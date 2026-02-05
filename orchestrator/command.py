from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import subprocess


@dataclass(frozen=True)
class CommandOutput:
    args: tuple[str, ...]
    cwd: str
    returncode: int
    stdout: str
    stderr: str


class CommandError(RuntimeError):
    def __init__(self, output: CommandOutput):
        message = (
            f"command failed ({output.returncode}): {' '.join(output.args)}\n"
            f"cwd={output.cwd}\n"
            f"stdout:\n{output.stdout}\n"
            f"stderr:\n{output.stderr}"
        )
        super().__init__(message)
        self.output = output


class CommandRunner:
    def run(
        self,
        args: Iterable[str],
        cwd: Path,
        timeout_sec: int | None = None,
        check: bool = False,
    ) -> CommandOutput:
        arg_list = [str(arg) for arg in args]
        completed = subprocess.run(
            arg_list,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        output = CommandOutput(
            args=tuple(arg_list),
            cwd=str(cwd),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if check and output.returncode != 0:
            raise CommandError(output)
        return output

    def run_shell(
        self,
        command: str,
        cwd: Path,
        timeout_sec: int | None = None,
        check: bool = False,
    ) -> CommandOutput:
        completed = subprocess.run(
            ["zsh", "-lc", command],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        output = CommandOutput(
            args=("zsh", "-lc", command),
            cwd=str(cwd),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if check and output.returncode != 0:
            raise CommandError(output)
        return output
