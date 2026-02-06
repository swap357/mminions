from __future__ import annotations

from pathlib import Path
from . import command


def list_sessions() -> list[str]:
    result = command.run(["tmux", "ls", "-F", "#{session_name}"], cwd=Path.cwd())
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def session_exists(name: str) -> bool:
    return name in list_sessions()


def create_session(name: str, workdir: Path, cmd: str) -> None:
    command.run(["tmux", "new-session", "-d", "-s", name, "-c", str(workdir), cmd], cwd=workdir)


def kill_session(name: str) -> None:
    command.run(["tmux", "kill-session", "-t", name], cwd=Path.cwd())


def capture_pane(name: str, lines: int = 100) -> str:
    result = command.run(["tmux", "capture-pane", "-p", "-t", name, "-S", f"-{lines}"], cwd=Path.cwd())
    return result.stdout if result.returncode == 0 else ""
