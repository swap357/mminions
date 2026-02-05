from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile

from .command import CommandRunner


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    passed: bool
    details: str


@dataclass(frozen=True)
class PreflightResult:
    checks: list[PreflightCheck]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def _has_command(command: str) -> bool:
    return shutil.which(command) is not None


def _check_git_repo(command_runner: CommandRunner, repo_path: Path) -> PreflightCheck:
    output = command_runner.run(["git", "-C", str(repo_path), "rev-parse", "--is-inside-work-tree"], cwd=repo_path)
    passed = output.returncode == 0 and output.stdout.strip() == "true"
    return PreflightCheck(
        name="repo_path",
        passed=passed,
        details=output.stdout.strip() or output.stderr.strip() or "invalid git repository",
    )


def _check_codex_auth(command_runner: CommandRunner, repo_path: Path) -> PreflightCheck:
    with tempfile.NamedTemporaryFile(prefix="mminions-codex-auth-", suffix=".txt", delete=True) as temp_file:
        output = command_runner.run(
            [
                "codex",
                "exec",
                "reply with OK",
                "-s",
                "read-only",
                "--skip-git-repo-check",
                "-C",
                str(repo_path),
                "-o",
                temp_file.name,
            ],
            cwd=repo_path,
            timeout_sec=30,
        )
    details = (output.stderr or output.stdout).strip()
    if output.returncode == 0:
        return PreflightCheck(name="codex_auth", passed=True, details="codex exec succeeded")
    login_needed = "login" in details.lower() or "auth" in details.lower()
    reason = details if details else "codex exec failed"
    if login_needed:
        reason = f"codex authentication required: {reason}"
    return PreflightCheck(name="codex_auth", passed=False, details=reason)


def run_preflight(command_runner: CommandRunner, repo_path: Path) -> PreflightResult:
    has_codex = _has_command("codex")
    has_tmux = _has_command("tmux")
    has_git = _has_command("git")
    checks = [
        PreflightCheck(name="codex", passed=has_codex, details="codex found" if has_codex else "codex not found in PATH"),
        PreflightCheck(name="tmux", passed=has_tmux, details="tmux found" if has_tmux else "tmux not found in PATH"),
        PreflightCheck(name="git", passed=has_git, details="git found" if has_git else "git not found in PATH"),
    ]

    if repo_path.is_absolute() and repo_path.exists():
        checks.append(PreflightCheck(name="repo_exists", passed=True, details="repo path exists"))
    else:
        checks.append(PreflightCheck(name="repo_exists", passed=False, details="repo path must be an absolute existing path"))
        return PreflightResult(checks=checks)

    checks.append(_check_git_repo(command_runner, repo_path))

    if all(check.passed for check in checks):
        checks.append(_check_codex_auth(command_runner, repo_path))

    return PreflightResult(checks=checks)
