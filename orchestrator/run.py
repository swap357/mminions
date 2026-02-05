from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import argparse
import shlex
import time

from .artifacts import ArtifactStore
from .command import CommandRunner


@dataclass(frozen=True)
class LauncherConfig:
    issue_url: str
    repo_path: Path
    runs_root: Path
    min_workers: int
    max_workers: int
    timeout_sec: int
    repro_validation_runs: int
    repro_min_matches: int
    validation_python_version: str
    worker_model: str
    manager_model: str
    detach: bool


def make_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run-{stamp}"


def _manager_session_name(run_id: str) -> str:
    return f"codorch-{run_id}-manager"


def launch_manager(config: LauncherConfig) -> tuple[str, Path]:
    run_id = make_run_id()
    runs_root = config.runs_root.resolve()
    runs_root.mkdir(parents=True, exist_ok=True)
    artifact_store = ArtifactStore(runs_root, run_id)
    paths = artifact_store.initialize_contract()

    session_name = _manager_session_name(run_id)

    command = (
        "python -m orchestrator.manager "
        f"--run-id {shlex.quote(run_id)} "
        f"--issue-url {shlex.quote(config.issue_url)} "
        f"--repo-path {shlex.quote(str(config.repo_path.resolve()))} "
        f"--runs-root {shlex.quote(str(runs_root))} "
        f"--min-workers {config.min_workers} "
        f"--max-workers {config.max_workers} "
        f"--timeout-sec {config.timeout_sec} "
        f"--repro-validation-runs {config.repro_validation_runs} "
        f"--repro-min-matches {config.repro_min_matches} "
        f"--validation-python-version {shlex.quote(config.validation_python_version)} "
        f"--worker-model {shlex.quote(config.worker_model)} "
        f"--manager-model {shlex.quote(config.manager_model)}"
    )

    runner = CommandRunner()
    existing = runner.run(["tmux", "ls", "-F", "#{session_name}"], cwd=config.repo_path)
    if existing.returncode == 0 and session_name in existing.stdout:
        runner.run(["tmux", "kill-session", "-t", session_name], cwd=config.repo_path)

    create_result = runner.run(["tmux", "new-session", "-d", "-s", session_name, "-c", str(config.repo_path), command], cwd=config.repo_path)
    if create_result.returncode != 0:
        raise RuntimeError(create_result.stderr or create_result.stdout or "failed to create manager tmux session")

    return run_id, paths.run_done_json


def wait_for_run_done(run_done_json: Path, timeout_sec: int) -> bool:
    started = time.time()
    while time.time() - started <= timeout_sec:
        if run_done_json.exists():
            return True
        time.sleep(2)
    return False


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compatibility launcher: start manager in tmux")
    parser.add_argument("--issue-url", required=True)
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--runs-root", default="runs")
    parser.add_argument("--min-workers", type=int, default=2)
    parser.add_argument("--max-workers", type=int, default=6)
    parser.add_argument("--timeout-sec", type=int, default=300)
    parser.add_argument("--repro-validation-runs", type=int, default=5)
    parser.add_argument("--repro-min-matches", type=int, default=1)
    parser.add_argument("--validation-python-version", default="3.12")
    parser.add_argument("--worker-model", default="")
    parser.add_argument("--manager-model", default="")
    parser.add_argument("--detach", action="store_true", default=False)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    config = LauncherConfig(
        issue_url=args.issue_url,
        repo_path=Path(args.repo_path).resolve(),
        runs_root=Path(args.runs_root).resolve(),
        min_workers=max(2, args.min_workers),
        max_workers=min(6, max(2, args.max_workers)),
        timeout_sec=max(60, args.timeout_sec),
        repro_validation_runs=max(1, args.repro_validation_runs),
        repro_min_matches=max(1, min(args.repro_min_matches, max(1, args.repro_validation_runs))),
        validation_python_version=str(args.validation_python_version).strip() or "3.12",
        worker_model=str(args.worker_model).strip(),
        manager_model=str(args.manager_model).strip(),
        detach=args.detach,
    )

    run_id, run_done_json = launch_manager(config)
    print(f"run_id={run_id}")
    print(f"manager_session=codorch-{run_id}-manager")
    print(f"run_done={run_done_json}")

    if config.detach:
        return 0

    completed = wait_for_run_done(run_done_json, timeout_sec=config.timeout_sec)
    if not completed:
        print("run did not finish before timeout")
        return 1

    print(f"run finished: {run_done_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
