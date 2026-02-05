from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .command import CommandRunner, CommandError


@dataclass(frozen=True)
class WorktreeInfo:
    worker_id: str
    path: Path


class WorktreeManager:
    def __init__(self, command_runner: CommandRunner, repo_path: Path) -> None:
        self.command_runner = command_runner
        self.repo_path = repo_path

    def create(self, worker_id: str, path: Path) -> WorktreeInfo:
        output = self.command_runner.run(["git", "-C", str(self.repo_path), "worktree", "add", str(path), "-d"], cwd=self.repo_path)
        if output.returncode != 0 and "already exists" not in (output.stderr or ""):
            raise CommandError(output)
        return WorktreeInfo(worker_id=worker_id, path=path)

    def remove(self, path: Path) -> None:
        self.command_runner.run(["git", "-C", str(self.repo_path), "worktree", "remove", "--force", str(path)], cwd=self.repo_path)

    def diff(self, path: Path) -> str:
        output = self.command_runner.run(["git", "-C", str(path), "diff", "HEAD"], cwd=path)
        return output.stdout
