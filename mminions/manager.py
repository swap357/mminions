from __future__ import annotations

from pathlib import Path
import argparse
import json
import time

from . import command, tmux, workers
from .config import Config, load_config
from .issue import fetch_issue, IssueParseError
from .types import IssueSpec, ReproCandidate, Hypothesis, RunResult, to_dict


def run_id() -> str:
    return time.strftime("run-%Y%m%d%H%M%S", time.gmtime())


def log(msg: str) -> None:
    print(msg, flush=True)


def setup_run_dir(runs_root: Path, rid: str) -> Path:
    run_dir = runs_root / rid
    (run_dir / "repro").mkdir(parents=True, exist_ok=True)
    (run_dir / "triage").mkdir(parents=True, exist_ok=True)
    (run_dir / "scripts").mkdir(parents=True, exist_ok=True)
    return run_dir


def create_worktree(repo: Path, path: Path) -> None:
    command.run(["git", "worktree", "add", str(path), "-d"], cwd=repo)


def remove_worktree(repo: Path, path: Path) -> None:
    command.run(["git", "worktree", "remove", "--force", str(path)], cwd=repo)


def launch_worker(
    rid: str,
    worker_id: str,
    role: str,
    prompt: str,
    run_dir: Path,
    repo: Path,
    model: str,
) -> tuple[str, Path, Path]:
    """Launch a worker in tmux. Returns (session_name, output_path, worktree_path)."""
    session = f"mm-{rid}-{worker_id}"
    output_path = run_dir / role / f"{worker_id}.json"
    worktree = Path(f"/tmp/mm-{rid}-{worker_id}")
    script_path = run_dir / "scripts" / f"{worker_id}.sh"

    create_worktree(repo, worktree)

    script = workers.make_worker_script(prompt, output_path, worktree, model)
    script_path.write_text(script)
    script_path.chmod(0o755)

    if tmux.session_exists(session):
        tmux.kill_session(session)
    tmux.create_session(session, worktree, str(script_path))

    return session, output_path, worktree


def wait_for_workers(sessions: list[str], timeout: int, poll: int = 5) -> dict[str, str]:
    """Wait for workers to finish. Returns {session: status}."""
    start = time.time()
    status = {s: "running" for s in sessions}

    while time.time() - start < timeout:
        active = [s for s in sessions if tmux.session_exists(s)]
        for s in sessions:
            if s not in active and status[s] == "running":
                status[s] = "finished"
                log(f"  {s}: finished")

        if not active:
            break
        time.sleep(poll)

    for s in sessions:
        if status[s] == "running":
            status[s] = "timeout"
            tmux.kill_session(s)
            log(f"  {s}: timeout")

    return status


def parse_repro_output(path: Path, worker_id: str) -> ReproCandidate | None:
    if not path.exists():
        return None
    try:
        raw = path.read_text()
        # Handle markdown-wrapped JSON
        if "```" in raw:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            raw = raw[start:end]
        data = json.loads(raw)
        return ReproCandidate(
            worker_id=worker_id,
            script=data.get("script", ""),
            oracle_command=data.get("oracle_command", ""),
            failure_signature=data.get("failure_signature", ""),
        )
    except (json.JSONDecodeError, KeyError):
        return None


def parse_triage_output(path: Path, worker_id: str) -> list[Hypothesis]:
    if not path.exists():
        return []
    try:
        raw = path.read_text()
        if "```" in raw:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            raw = raw[start:end]
        data = json.loads(raw)
        return [
            Hypothesis(
                worker_id=worker_id,
                mechanism=h.get("mechanism", ""),
                file=h.get("file", ""),
                line=int(h.get("line", 0)),
            )
            for h in data.get("hypotheses", [])
        ]
    except (json.JSONDecodeError, KeyError):
        return []


def run(issue_url: str, config: Config) -> RunResult:
    rid = run_id()
    log(f"[run] {rid}")

    # Fetch issue
    log("[issue] fetching")
    try:
        issue = fetch_issue(issue_url)
    except IssueParseError as e:
        log(f"[issue] failed: {e}")
        return RunResult(rid, "failed", None, [])

    log(f"[issue] {issue.owner}/{issue.repo}#{issue.number}: {issue.title}")

    # Setup
    run_dir = setup_run_dir(config.runs_root, rid)
    worktrees: list[Path] = []

    # Phase 1: Repro workers
    log(f"[repro] launching {config.workers} workers")
    repro_sessions = []
    repro_outputs = []

    for i in range(config.workers):
        wid = f"repro-w{i+1}"
        prompt = workers.repro_prompt(issue, wid)
        session, output, wt = launch_worker(
            rid, wid, "repro", prompt, run_dir, config.repo_path, config.model
        )
        repro_sessions.append(session)
        repro_outputs.append((wid, output))
        worktrees.append(wt)
        log(f"  {wid}: {session}")

    log("[repro] waiting")
    wait_for_workers(repro_sessions, config.timeout_sec)

    # Parse repro outputs
    candidates = []
    for wid, path in repro_outputs:
        if c := parse_repro_output(path, wid):
            candidates.append(c)
            log(f"  {wid}: got candidate")

    best_repro = candidates[0] if candidates else None
    if not best_repro:
        log("[repro] no valid candidates")
        for wt in worktrees:
            remove_worktree(config.repo_path, wt)
        return RunResult(rid, "no-repro", None, [])

    log(f"[repro] using {best_repro.worker_id}")

    # Phase 2: Triage workers
    log(f"[triage] launching {config.workers} workers")
    triage_sessions = []
    triage_outputs = []

    for i in range(config.workers):
        wid = f"triage-w{i+1}"
        prompt = workers.triage_prompt(issue, wid, best_repro.script)
        session, output, wt = launch_worker(
            rid, wid, "triage", prompt, run_dir, config.repo_path, config.model
        )
        triage_sessions.append(session)
        triage_outputs.append((wid, output))
        worktrees.append(wt)
        log(f"  {wid}: {session}")

    log("[triage] waiting")
    wait_for_workers(triage_sessions, config.timeout_sec)

    # Parse triage outputs
    hypotheses = []
    for wid, path in triage_outputs:
        hyps = parse_triage_output(path, wid)
        hypotheses.extend(hyps)
        if hyps:
            log(f"  {wid}: {len(hyps)} hypotheses")

    # Cleanup
    for wt in worktrees:
        remove_worktree(config.repo_path, wt)

    # Write result
    result = RunResult(rid, "ok", best_repro, hypotheses)
    result_path = run_dir / "result.json"
    result_path.write_text(json.dumps(to_dict(result), indent=2))

    log(f"[done] {run_dir}")
    return result


def main() -> int:
    config = load_config()

    parser = argparse.ArgumentParser(description="mminions manager")
    parser.add_argument("--issue-url", required=True)
    parser.add_argument("--repo-path", type=Path, default=config.repo_path)
    parser.add_argument("--runs-root", type=Path, default=config.runs_root)
    parser.add_argument("--workers", type=int, default=config.workers)
    parser.add_argument("--timeout", type=int, default=config.timeout_sec)
    parser.add_argument("--model", default=config.model)
    args = parser.parse_args()

    cfg = Config(
        repo_path=args.repo_path.resolve(),
        runs_root=args.runs_root.resolve(),
        workers=args.workers,
        timeout_sec=args.timeout,
        model=args.model,
    )

    result = run(args.issue_url, cfg)
    print(json.dumps(to_dict(result), indent=2))
    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
