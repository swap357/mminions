from __future__ import annotations

from pathlib import Path
import argparse
import os

from .artifacts import ArtifactStore
from .command import CommandRunner
from .sessions import require_sessions, resolve_session_name
from .tmux_supervisor import TmuxSupervisor


def cmd_status(args: argparse.Namespace) -> int:
    runs_root = Path(args.runs_root).resolve()
    try:
        sessions = require_sessions(args.run_id, runs_root)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1
    runner = CommandRunner()
    tmux = TmuxSupervisor(runner, cwd=Path.cwd())

    manager_name = sessions.get("manager", {}).get("session_name", "")
    workers = sessions.get("workers", {})

    print(f"run_id={args.run_id}")
    print(f"manager={manager_name} exists={tmux.session_exists(manager_name) if manager_name else False}")
    for worker_id, metadata in sorted(workers.items()):
        name = metadata.get("session_name", "")
        role = metadata.get("role", "")
        status = metadata.get("status", "unknown")
        exists = tmux.session_exists(name) if name else False
        print(f"{worker_id} role={role} session={name} status={status} exists={exists}")
    return 0


def cmd_attach(args: argparse.Namespace) -> int:
    runs_root = Path(args.runs_root).resolve()
    try:
        sessions = require_sessions(args.run_id, runs_root)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1
    session_name = resolve_session_name(sessions, args.worker)
    if not session_name:
        print(f"unknown worker: {args.worker}")
        return 1
    os.execvp("tmux", ["tmux", "attach", "-t", session_name])
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    runs_root = Path(args.runs_root).resolve()
    try:
        sessions = require_sessions(args.run_id, runs_root)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1
    session_name = resolve_session_name(sessions, args.worker)
    if not session_name:
        print(f"unknown worker: {args.worker}")
        return 1

    runner = CommandRunner()
    tmux = TmuxSupervisor(runner, cwd=Path.cwd())
    tmux.send_text(session_name, args.text, press_enter=True)
    print(f"sent to {session_name}")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    runs_root = Path(args.runs_root).resolve()
    store = ArtifactStore(runs_root, args.run_id)
    try:
        sessions = require_sessions(args.run_id, runs_root)
    except FileNotFoundError:
        sessions = {"manager": {}, "workers": {}}
    runner = CommandRunner()
    tmux = TmuxSupervisor(runner, cwd=Path.cwd())

    manager_name = sessions.get("manager", {}).get("session_name")
    if manager_name:
        tmux.kill_session(manager_name)

    for worker in sessions.get("workers", {}).values():
        name = worker.get("session_name")
        if name:
            tmux.kill_session(name)

    if not store.paths.run_done_json.exists():
        store.write_json(
            store.paths.run_done_json,
            {
                "run_id": args.run_id,
                "status": "stopped",
                "final_md": str(store.paths.final_md),
                "decision_json": str(store.paths.decision_json),
            },
        )
    print(f"stopped run {args.run_id}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="mminions helper CLI")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status")
    p_status.add_argument("--run-id", required=True)
    p_status.add_argument("--runs-root", default="runs")
    p_status.set_defaults(func=cmd_status)

    p_attach = sub.add_parser("attach")
    p_attach.add_argument("--run-id", required=True)
    p_attach.add_argument("--worker", required=True)
    p_attach.add_argument("--runs-root", default="runs")
    p_attach.set_defaults(func=cmd_attach)

    p_send = sub.add_parser("send")
    p_send.add_argument("--run-id", required=True)
    p_send.add_argument("--worker", required=True)
    p_send.add_argument("--text", required=True)
    p_send.add_argument("--runs-root", default="runs")
    p_send.set_defaults(func=cmd_send)

    p_stop = sub.add_parser("stop")
    p_stop.add_argument("--run-id", required=True)
    p_stop.add_argument("--runs-root", default="runs")
    p_stop.set_defaults(func=cmd_stop)

    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
