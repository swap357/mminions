from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex

from .command import CommandRunner


@dataclass(frozen=True)
class SessionInfo:
    name: str
    exists: bool


class TmuxSupervisor:
    def __init__(self, command_runner: CommandRunner, cwd: Path) -> None:
        self.command_runner = command_runner
        self.cwd = cwd

    def list_sessions(self, prefix: str | None = None) -> list[str]:
        output = self.command_runner.run(["tmux", "ls", "-F", "#{session_name}"], cwd=self.cwd)
        if output.returncode != 0:
            return []
        names = [line.strip() for line in output.stdout.splitlines() if line.strip()]
        if prefix is None:
            return names
        return [name for name in names if name.startswith(prefix)]

    def session_exists(self, name: str) -> bool:
        return name in set(self.list_sessions())

    def create_session(self, name: str, workdir: Path, command: str | None = None) -> None:
        args = ["tmux", "new-session", "-d", "-s", name, "-c", str(workdir)]
        if command:
            args.append(command)
        self.command_runner.run(args, cwd=self.cwd, check=True)

    def kill_session(self, name: str) -> None:
        self.command_runner.run(["tmux", "kill-session", "-t", name], cwd=self.cwd)

    def send_text(self, name: str, text: str, press_enter: bool = True) -> None:
        args = ["tmux", "send-keys", "-t", name, text]
        if press_enter:
            args.append("C-m")
        self.command_runner.run(args, cwd=self.cwd, check=True)

    def capture_pane(self, name: str, lines: int = 200) -> str:
        output = self.command_runner.run(["tmux", "capture-pane", "-p", "-t", name, "-S", f"-{lines}"], cwd=self.cwd)
        if output.returncode != 0:
            return ""
        return output.stdout

    @staticmethod
    def attach_command(name: str) -> str:
        return f"tmux attach -t {shlex.quote(name)}"
