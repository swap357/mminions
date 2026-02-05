from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import argparse
import json
import time

from .artifacts import ArtifactStore
from .command import CommandRunner
from .issue import IssueParseError, fetch_issue_json, normalize_issue_spec, write_issue_spec
from .preflight import run_preflight
from .repro import choose_best_candidate, minimize_candidate, parse_repro_candidate, validate_candidate
from .supervision_loop import SupervisionLoop, WorkerWatchState
from .tmux_supervisor import TmuxSupervisor
from .triage import parse_triage_output, rank_hypotheses, top_hypotheses
from .types import ReproCandidate, RunDecision, dataclass_to_primitive
from .workers import build_codex_exec_script, build_repro_prompt, build_triage_prompt
from .worktree import WorktreeManager


@dataclass(frozen=True)
class ManagerConfig:
    run_id: str
    issue_url: str
    repo_path: Path
    runs_root: Path
    min_workers: int = 2
    max_workers: int = 6
    timeout_sec: int = 300
    poll_interval_sec: int = 5


class Manager:
    def __init__(self, config: ManagerConfig) -> None:
        self.config = config
        self.command_runner = CommandRunner()
        self.artifacts = ArtifactStore(config.runs_root, config.run_id)
        self.paths = self.artifacts.initialize_contract()
        self.tmux = TmuxSupervisor(self.command_runner, cwd=config.repo_path)
        self.worktrees = WorktreeManager(self.command_runner, repo_path=config.repo_path)
        self.supervisor = SupervisionLoop(self.tmux, stall_timeout_sec=max(45, config.timeout_sec // 3))

    @property
    def manager_session_name(self) -> str:
        return f"codorch-{self.config.run_id}-manager"

    def _write_sessions(self, worker_sessions: dict[str, dict[str, Any]]) -> None:
        payload = {
            "manager": {
                "session_name": self.manager_session_name,
                "run_id": self.config.run_id,
                "issue_url": self.config.issue_url,
            },
            "workers": worker_sessions,
        }
        self.artifacts.write_json(self.paths.sessions_json, payload)

    def _finalize(self, decision: RunDecision, extra: dict[str, Any] | None = None) -> RunDecision:
        extra = extra or {}
        decision_payload = dataclass_to_primitive(decision)
        decision_payload.update(extra)
        self.artifacts.write_json(self.paths.decision_json, decision_payload)

        final_lines = [
            f"# mminions run {self.config.run_id}",
            "",
            f"- issue: {self.config.issue_url}",
            f"- status: {decision.status}",
            f"- selected repro candidate: {decision.selected_repro_candidate_id or 'none'}",
            "",
            "## Rationale",
            decision.rationale,
            "",
            "## Top hypotheses",
        ]
        if decision.top_hypotheses:
            for idx, hypothesis in enumerate(decision.top_hypotheses, start=1):
                final_lines.append(f"{idx}. {hypothesis}")
        else:
            final_lines.append("1. none")

        if decision.next_fix_targets:
            final_lines.extend(["", "## Suggested next fix targets"])
            for idx, target in enumerate(decision.next_fix_targets, start=1):
                final_lines.append(f"{idx}. {target}")

        if decision.diagnostics:
            final_lines.extend(["", "## Diagnostics"])
            for diagnostic in decision.diagnostics:
                final_lines.append(f"- {diagnostic}")

        self.paths.final_md.write_text("\n".join(final_lines) + "\n", encoding="utf-8")

        run_done = {
            "run_id": self.config.run_id,
            "status": decision.status,
            "decision_json": str(self.paths.decision_json),
            "final_md": str(self.paths.final_md),
            "completed_at": decision.created_at,
        }
        self.artifacts.write_json(self.paths.run_done_json, run_done)
        return decision

    def _worker_count_sequence(self) -> list[int]:
        sequence = [self.config.min_workers]
        for size in (4, 6):
            if self.config.min_workers < size <= self.config.max_workers:
                sequence.append(size)
        if self.config.max_workers not in sequence:
            sequence.append(self.config.max_workers)
        return sorted(set(sequence))

    def _launch_workers(self, role: str, count: int, issue_spec, minimal_repro: str | None = None) -> tuple[dict[str, dict[str, Any]], list[Path]]:
        worker_sessions: dict[str, dict[str, Any]] = {}
        output_paths: list[Path] = []

        for idx in range(1, count + 1):
            worker_id = f"w{idx}"
            session_name = f"codorch-{self.config.run_id}-{worker_id}"
            script_path = self.paths.scripts_dir / f"{role.lower()}-{worker_id}.sh"
            output_path = (
                self.paths.repro_candidates_dir / f"{worker_id}.json"
                if role == "REPRO_BUILDER"
                else self.paths.triage_dir / f"{worker_id}.json"
            )
            output_paths.append(output_path)

            worktree_path = Path(f"/tmp/mminions-{self.config.run_id}-{worker_id}")
            self.worktrees.create(worker_id=worker_id, path=worktree_path)

            if role == "REPRO_BUILDER":
                prompt = build_repro_prompt(issue_spec=issue_spec, worker_id=worker_id)
            else:
                prompt = build_triage_prompt(
                    issue_spec=issue_spec,
                    worker_id=worker_id,
                    minimal_repro=minimal_repro or "",
                    code_search_hints=issue_spec.target_paths,
                )

            build_codex_exec_script(
                prompt=prompt,
                output_path=output_path,
                script_path=script_path,
                worktree_path=worktree_path,
            )

            if self.tmux.session_exists(session_name):
                self.tmux.kill_session(session_name)
            self.tmux.create_session(name=session_name, workdir=self.config.repo_path, command=str(script_path))

            worker_sessions[worker_id] = {
                "session_name": session_name,
                "role": role,
                "worktree_path": str(worktree_path),
                "output_path": str(output_path),
                "script_path": str(script_path),
            }

        return worker_sessions, output_paths

    def _wait_for_workers(self, worker_sessions: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        watches: dict[str, WorkerWatchState] = {}
        for worker_id, metadata in worker_sessions.items():
            watches[worker_id] = WorkerWatchState(
                session_name=metadata["session_name"],
                script_path=Path(metadata["script_path"]),
            )

        start = time.time()
        while True:
            active = []
            for worker_id, watch in watches.items():
                watch = self.supervisor.tick(watch, workdir=self.config.repo_path)
                watches[worker_id] = watch

                if watch.failed:
                    worker_sessions[worker_id]["status"] = "failed"
                    continue

                session_exists = self.tmux.session_exists(watch.session_name)
                if session_exists:
                    active.append(worker_id)
                else:
                    worker_sessions[worker_id]["status"] = "finished"

            if not active:
                break
            if time.time() - start >= self.config.timeout_sec:
                for worker_id in active:
                    session = watches[worker_id].session_name
                    self.tmux.kill_session(session)
                    worker_sessions[worker_id]["status"] = "timeout"
                break
            time.sleep(self.config.poll_interval_sec)

        return worker_sessions

    def _validate_candidates(self, issue_spec, output_paths: list[Path]) -> list[ReproCandidate]:
        candidates: list[ReproCandidate] = []
        for path in output_paths:
            worker_id = path.stem
            try:
                candidate = parse_repro_candidate(worker_id=worker_id, output_path=path)
            except Exception as exc:
                diagnostic = f"failed to parse candidate from {path.name}: {exc}"
                self._append_diagnostic(diagnostic)
                continue
            if candidate is None:
                continue

            candidate_script_path = self.paths.repro_candidates_dir / f"{candidate.candidate_id}.{candidate.file_extension}"
            validation = validate_candidate(
                candidate=candidate,
                issue_spec=issue_spec,
                repo_path=self.config.repo_path,
                candidate_script_path=candidate_script_path,
                command_runner=self.command_runner,
                runs=5,
                timeout_sec=min(60, self.config.timeout_sec),
            )
            candidate = ReproCandidate(
                candidate_id=candidate.candidate_id,
                worker_id=candidate.worker_id,
                script=candidate.script,
                setup_commands=candidate.setup_commands,
                oracle_command=candidate.oracle_command,
                claimed_failure_signature=candidate.claimed_failure_signature,
                file_extension=candidate.file_extension,
                validation=validation,
            )
            self.artifacts.write_json(path, dataclass_to_primitive(candidate))
            candidates.append(candidate)

        return candidates

    def _append_diagnostic(self, text: str) -> None:
        existing = self.artifacts.read_json(self.paths.decision_json)
        diagnostics = existing.get("diagnostics", []) if isinstance(existing, dict) else []
        diagnostics.append(text)
        payload = existing if isinstance(existing, dict) else {}
        payload["diagnostics"] = diagnostics
        self.artifacts.write_json(self.paths.decision_json, payload)

    def _cleanup_worktrees(self, worker_sessions: dict[str, dict[str, Any]]) -> None:
        for metadata in worker_sessions.values():
            path = Path(metadata.get("worktree_path", ""))
            if path.exists():
                self.worktrees.remove(path)

    @staticmethod
    def _triage_disagreement_high(hypotheses) -> bool:
        if not hypotheses:
            return False
        mechanisms = {
            hypothesis.mechanism.strip().lower()
            for hypothesis in hypotheses
            if hypothesis.mechanism.strip()
        }
        if len(mechanisms) <= 1:
            return False
        top_scores = [hyp.score or 0.0 for hyp in hypotheses[:2]]
        if len(top_scores) < 2:
            return False
        return abs(top_scores[0] - top_scores[1]) <= 0.15

    def run(self) -> RunDecision:
        diagnostics: list[str] = []

        preflight_result = run_preflight(self.command_runner, self.config.repo_path)
        self.artifacts.write_json(
            self.paths.decision_json,
            {
                "preflight": [asdict(check) for check in preflight_result.checks],
                "diagnostics": [],
            },
        )
        if not preflight_result.passed:
            diagnostics.extend([f"preflight failed: {check.name} -> {check.details}" for check in preflight_result.checks if not check.passed])
            decision = RunDecision(
                status="needs-human",
                selected_repro_candidate_id=None,
                rationale="preflight failed",
                top_hypotheses=[],
                next_fix_targets=[],
                diagnostics=diagnostics,
            )
            return self._finalize(decision)

        try:
            issue_payload = fetch_issue_json(self.config.issue_url)
            issue_spec = normalize_issue_spec(self.config.issue_url, issue_payload)
        except IssueParseError as exc:
            decision = RunDecision(
                status="needs-human",
                selected_repro_candidate_id=None,
                rationale="issue parsing failed",
                top_hypotheses=[],
                next_fix_targets=[],
                diagnostics=[str(exc)],
            )
            return self._finalize(decision)

        write_issue_spec(issue_spec=issue_spec, path=self.paths.issue_json)

        if issue_spec.status != "ok":
            decision = RunDecision(
                status="needs-human",
                selected_repro_candidate_id=None,
                rationale="issue lacks strong machine-testable failure signals",
                top_hypotheses=[],
                next_fix_targets=[],
                diagnostics=[issue_spec.needs_human_reason or "unknown issue spec error"],
            )
            return self._finalize(decision)

        accepted_candidates: list[ReproCandidate] = []
        worker_sessions: dict[str, dict[str, Any]] = {}
        repro_output_paths: list[Path] = []

        for worker_count in self._worker_count_sequence():
            worker_sessions, repro_output_paths = self._launch_workers(
                role="REPRO_BUILDER",
                count=worker_count,
                issue_spec=issue_spec,
            )
            self._write_sessions(worker_sessions)
            worker_sessions = self._wait_for_workers(worker_sessions)
            self._write_sessions(worker_sessions)
            accepted_candidates = self._validate_candidates(issue_spec, repro_output_paths)
            if choose_best_candidate(accepted_candidates, issue_spec):
                break

        best = choose_best_candidate(accepted_candidates, issue_spec)
        if best is None:
            self._cleanup_worktrees(worker_sessions)
            decision = RunDecision(
                status="needs-human",
                selected_repro_candidate_id=None,
                rationale="no deterministic reproducer met the acceptance gate (>=4/5 runs)",
                top_hypotheses=[],
                next_fix_targets=[],
                diagnostics=diagnostics,
            )
            return self._finalize(decision)

        semantic_output_path = self.paths.repro_dir / "semantic_reduce_output.txt"
        minimal_repro_path = self.artifacts.minimal_repro_path(best.file_extension)
        minimized = minimize_candidate(
            candidate=best,
            issue_spec=issue_spec,
            repo_path=self.config.repo_path,
            command_runner=self.command_runner,
            semantic_output_path=semantic_output_path,
            minimal_output_path=minimal_repro_path,
            timeout_sec=min(60, self.config.timeout_sec),
        )

        if not minimized.validation or not minimized.validation.passed:
            minimized = best
            minimal_repro_path = self.artifacts.minimal_repro_path(best.file_extension)
            minimal_repro_path.write_text(best.script, encoding="utf-8")

        self.artifacts.write_json(
            self.paths.repro_dir / "selected_candidate.json",
            dataclass_to_primitive(minimized),
        )

        triage_sessions: dict[str, dict[str, Any]] = {}
        triage_hypotheses = []

        for worker_count in self._worker_count_sequence():
            triage_sessions, triage_output_paths = self._launch_workers(
                role="TRIAGER",
                count=worker_count,
                issue_spec=issue_spec,
                minimal_repro=minimized.script,
            )
            self._write_sessions(triage_sessions)
            triage_sessions = self._wait_for_workers(triage_sessions)
            self._write_sessions(triage_sessions)

            triage_hypotheses = []
            for output in triage_output_paths:
                triage_hypotheses.extend(parse_triage_output(worker_id=output.stem, output_path=output))

            ranked = rank_hypotheses(
                repo_path=self.config.repo_path,
                hypotheses=triage_hypotheses,
                repro_text=minimized.script,
            )
            disagreement_high = self._triage_disagreement_high(ranked)
            if ranked and (not disagreement_high or worker_count >= self.config.max_workers):
                triage_hypotheses = ranked
                break
            if not ranked and worker_count >= self.config.max_workers:
                triage_hypotheses = ranked
                break

        top = top_hypotheses(triage_hypotheses, limit=3)

        triage_payload = {
            "hypotheses": [dataclass_to_primitive(hypothesis) for hypothesis in triage_hypotheses],
            "top": [dataclass_to_primitive(hypothesis) for hypothesis in top],
        }
        self.artifacts.write_json(self.paths.triage_hypotheses_json, triage_payload)

        next_fix_targets: list[str] = []
        for hypothesis in top:
            next_fix_targets.extend([f"{ev.file}:{ev.line}" for ev in hypothesis.evidence[:1]])

        self._cleanup_worktrees(worker_sessions)
        self._cleanup_worktrees(triage_sessions)

        decision = RunDecision(
            status="ok",
            selected_repro_candidate_id=minimized.candidate_id,
            rationale="selected highest-scoring deterministic reproducer, then merged triage hypotheses with evidence validation",
            top_hypotheses=[hyp.mechanism for hyp in top],
            next_fix_targets=next_fix_targets,
            diagnostics=diagnostics,
        )
        self._finalize(
            decision,
            extra={
                "repro": {
                    "path": str(minimal_repro_path),
                    "oracle_command": minimized.oracle_command,
                    "claimed_failure_signature": minimized.claimed_failure_signature,
                    "validation": dataclass_to_primitive(minimized.validation),
                },
            },
        )
        return decision


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run mminions manager")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--issue-url", required=True)
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--runs-root", default="runs")
    parser.add_argument("--min-workers", type=int, default=2)
    parser.add_argument("--max-workers", type=int, default=6)
    parser.add_argument("--timeout-sec", type=int, default=300)
    parser.add_argument("--poll-interval-sec", type=int, default=5)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    config = ManagerConfig(
        run_id=args.run_id,
        issue_url=args.issue_url,
        repo_path=Path(args.repo_path).resolve(),
        runs_root=Path(args.runs_root).resolve(),
        min_workers=args.min_workers,
        max_workers=args.max_workers,
        timeout_sec=args.timeout_sec,
        poll_interval_sec=args.poll_interval_sec,
    )

    manager = Manager(config)
    decision = manager.run()

    print(json.dumps(dataclass_to_primitive(decision), indent=2))
    return 0 if decision.status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
