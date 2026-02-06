from __future__ import annotations

from pathlib import Path
import argparse
import os

from . import tmux


def cmd_ls(args: argparse.Namespace) -> int:
    """List active mminions sessions."""
    sessions = [s for s in tmux.list_sessions() if s.startswith("mm-")]
    for s in sessions:
        print(s)
    return 0


def cmd_attach(args: argparse.Namespace) -> int:
    """Attach to a session."""
    os.execvp("tmux", ["tmux", "attach", "-t", args.session])
    return 0


def cmd_kill(args: argparse.Namespace) -> int:
    """Kill a session or all mminions sessions."""
    if args.all:
        sessions = [s for s in tmux.list_sessions() if s.startswith("mm-")]
        for s in sessions:
            tmux.kill_session(s)
            print(f"killed {s}")
    else:
        tmux.kill_session(args.session)
        print(f"killed {args.session}")
    return 0


def cmd_tail(args: argparse.Namespace) -> int:
    """Show recent output from a session."""
    output = tmux.capture_pane(args.session, lines=args.lines)
    print(output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="mminions CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ls", help="list sessions").set_defaults(func=cmd_ls)

    p_attach = sub.add_parser("attach", help="attach to session")
    p_attach.add_argument("session")
    p_attach.set_defaults(func=cmd_attach)

    p_kill = sub.add_parser("kill", help="kill session(s)")
    p_kill.add_argument("session", nargs="?")
    p_kill.add_argument("--all", action="store_true")
    p_kill.set_defaults(func=cmd_kill)

    p_tail = sub.add_parser("tail", help="show session output")
    p_tail.add_argument("session")
    p_tail.add_argument("-n", "--lines", type=int, default=50)
    p_tail.set_defaults(func=cmd_tail)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
