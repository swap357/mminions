from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
import json

from orchestrator.command import CommandOutput, CommandRunner
from orchestrator.types import dataclass_to_primitive


NumpyConvolveMode = Literal["offline", "live"]
NumpyConvolveStatus = Literal["passed", "failed", "skipped"]
BeforeOracleState = Literal["bug_present", "unexpected"]
AfterOracleState = Literal["fixed", "not_fixed", "not_run"]


@dataclass(frozen=True)
class NumpyConvolveEvalConfig:
    numpy_repo_path: Path
    runs_root: Path
    issue_url: str = "https://github.com/numpy/numpy/issues/30272"
    bug_commit: str = "9f0519e83247b8a1b46c12fb583d4d575d992bd7"
    reference_fix_commit: str = "3a811fb9af105372da2d07d83e77ae085d51f54e"
    mode: NumpyConvolveMode = "offline"
    python_version: str = "3.12"
    max_runtime_sec: int = 900


@dataclass(frozen=True)
class NumpyConvolveEvalResult:
    status: NumpyConvolveStatus
    before_oracle: BeforeOracleState
    after_oracle: AfterOracleState
    codex_invoked: bool
    skip_reason: str | None
    artifacts_dir: Path
    candidate_diff_path: Path | None


class NumpyConvolveEvaluator:
    def __init__(self, config: NumpyConvolveEvalConfig, command_runner: CommandRunner | None = None) -> None:
        self.config = config
        self.command_runner = command_runner or CommandRunner()
        self._created_worktrees: list[Path] = []

    def run(self) -> NumpyConvolveEvalResult:
        started_at = datetime.now(timezone.utc).isoformat()
        artifacts_dir = self._create_artifacts_dir()

        status: NumpyConvolveStatus = "failed"
        before_state: BeforeOracleState = "unexpected"
        after_state: AfterOracleState = "not_run"
        skip_reason: str | None = None
        codex_invoked = False
        candidate_diff_path: Path | None = None

        before_worktree = artifacts_dir / "worktrees" / "before"
        candidate_worktree = artifacts_dir / "worktrees" / "candidate"
        reference_worktree = artifacts_dir / "worktrees" / "reference_fix"

        self._write_json(
            artifacts_dir / "metadata.json",
            {
                "issue_url": self.config.issue_url,
                "bug_commit": self.config.bug_commit,
                "reference_fix_commit": self.config.reference_fix_commit,
                "mode": self.config.mode,
                "python_version": self.config.python_version,
                "max_runtime_sec": self.config.max_runtime_sec,
                "started_at": started_at,
            },
        )

        try:
            self._validate_inputs()
            self._create_worktree(before_worktree, self.config.bug_commit)
            self._create_worktree(candidate_worktree, self.config.bug_commit)

            if self.config.mode == "live":
                self._create_worktree(reference_worktree, self.config.reference_fix_commit)

            if self.config.mode == "offline":
                before_payload = self._offline_before_oracle()
                self._write_json(artifacts_dir / "before_oracle.json", before_payload)
                before_state = self._classify_before_oracle(before_payload)
                after_state = "not_run"
                status = "passed" if before_state == "bug_present" else "failed"
            else:
                auth_ok, auth_reason = self._check_codex_auth(candidate_worktree)
                self._write_json(
                    artifacts_dir / "codex_auth.json",
                    {
                        "ok": auth_ok,
                        "reason": auth_reason,
                    },
                )
                if not auth_ok:
                    status = "skipped"
                    skip_reason = auth_reason or "codex auth unavailable"
                else:
                    python_bin = self._bootstrap_runtime(artifacts_dir)

                    before_payload = self._run_oracle(python_bin, before_worktree, artifacts_dir / "before_oracle.json")
                    before_state = self._classify_before_oracle(before_payload)

                    self._run_codex_fix(candidate_worktree, artifacts_dir / "codex_output.txt")
                    codex_invoked = True

                    candidate_diff_path = artifacts_dir / "candidate.patch"
                    diff_text = self._capture_candidate_diff(candidate_worktree, candidate_diff_path)
                    patch_ok, patch_error = self._validate_candidate_patch(candidate_worktree, diff_text)
                    if not patch_ok:
                        self._write_json(
                            artifacts_dir / "candidate_patch_validation.json",
                            {
                                "ok": False,
                                "error": patch_error,
                            },
                        )
                        status = "failed"
                    else:
                        self._write_json(
                            artifacts_dir / "candidate_patch_validation.json",
                            {
                                "ok": True,
                                "error": None,
                            },
                        )
                        after_payload = self._run_oracle(python_bin, candidate_worktree, artifacts_dir / "after_oracle.json")
                        after_state = self._classify_after_oracle(after_payload)

                        reference_payload = self._run_oracle(
                            python_bin,
                            reference_worktree,
                            artifacts_dir / "reference_oracle.json",
                        )
                        self._write_json(artifacts_dir / "reference_oracle_summary.json", reference_payload)

                        status = "passed" if (before_state == "bug_present" and after_state == "fixed") else "failed"
        except Exception as exc:
            status = "failed"
            self._write_json(
                artifacts_dir / "error.json",
                {
                    "error": str(exc),
                    "type": exc.__class__.__name__,
                },
            )
        finally:
            self._cleanup_worktrees()

        result = NumpyConvolveEvalResult(
            status=status,
            before_oracle=before_state,
            after_oracle=after_state,
            codex_invoked=codex_invoked,
            skip_reason=skip_reason,
            artifacts_dir=artifacts_dir,
            candidate_diff_path=candidate_diff_path,
        )
        self._write_json(
            artifacts_dir / "summary.json",
            {
                **dataclass_to_primitive(result),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return result

    def _validate_inputs(self) -> None:
        if self.config.mode not in {"offline", "live"}:
            raise ValueError(f"invalid mode: {self.config.mode}")
        if not self.config.numpy_repo_path.is_absolute():
            raise ValueError("numpy_repo_path must be absolute")
        if not self.config.numpy_repo_path.exists():
            raise ValueError(f"numpy_repo_path not found: {self.config.numpy_repo_path}")
        repo_check = self.command_runner.run(
            ["git", "-C", str(self.config.numpy_repo_path), "rev-parse", "--is-inside-work-tree"],
            cwd=self.config.numpy_repo_path,
        )
        if repo_check.returncode != 0 or repo_check.stdout.strip() != "true":
            raise RuntimeError("numpy_repo_path is not a git repo")

    def _create_artifacts_dir(self) -> Path:
        self.config.runs_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        run_dir = self.config.runs_root / f"numpy-convolve-eval-{stamp}"
        suffix = 0
        while run_dir.exists():
            suffix += 1
            run_dir = self.config.runs_root / f"numpy-convolve-eval-{stamp}-{suffix}"
        (run_dir / "worktrees").mkdir(parents=True, exist_ok=True)
        return run_dir

    def _create_worktree(self, path: Path, commit: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        output = self.command_runner.run(
            [
                "git",
                "-C",
                str(self.config.numpy_repo_path),
                "worktree",
                "add",
                "--detach",
                str(path),
                commit,
            ],
            cwd=self.config.numpy_repo_path,
        )
        if output.returncode != 0:
            raise RuntimeError(output.stderr or output.stdout or f"failed to create worktree {path}")
        self._created_worktrees.append(path)

    def _cleanup_worktrees(self) -> None:
        for path in reversed(self._created_worktrees):
            self.command_runner.run(
                ["git", "-C", str(self.config.numpy_repo_path), "worktree", "remove", "--force", str(path)],
                cwd=self.config.numpy_repo_path,
            )
        self._created_worktrees = []

    def _offline_before_oracle(self) -> dict[str, Any]:
        return {
            "first_error": "v cannot be empty",
            "second_error": "v cannot be empty",
            "status": "bug_present",
            "source": "offline-fixture",
        }

    def _check_codex_auth(self, worktree: Path) -> tuple[bool, str]:
        output_path = worktree / ".mminions-codex-auth.txt"
        output = self.command_runner.run(
            [
                "codex",
                "exec",
                "reply with OK",
                "-s",
                "read-only",
                "--skip-git-repo-check",
                "-C",
                str(worktree),
                "-o",
                str(output_path),
            ],
            cwd=worktree,
            timeout_sec=45,
        )
        details = (output.stderr or output.stdout).strip()
        if output.returncode == 0:
            return True, "codex auth ok"
        if not details:
            details = "codex auth check failed"
        lowered = details.lower()
        if "auth" in lowered or "login" in lowered or "permission denied" in lowered:
            return False, details
        return False, details

    def _bootstrap_runtime(self, artifacts_dir: Path) -> Path:
        venv_dir = artifacts_dir / ".venv"
        venv_create = self.command_runner.run(
            ["uv", "venv", "--python", self.config.python_version, str(venv_dir)],
            cwd=artifacts_dir,
            timeout_sec=min(self.config.max_runtime_sec, 300),
        )
        if venv_create.returncode != 0:
            raise RuntimeError(venv_create.stderr or venv_create.stdout or "failed to create uv venv")

        python_bin = venv_dir / "bin" / "python"
        if not python_bin.exists():
            raise RuntimeError(f"venv python not found: {python_bin}")

        self._run_checked(
            [str(python_bin), "-m", "pip", "install", "--upgrade", "pip"],
            cwd=artifacts_dir,
            timeout_sec=min(self.config.max_runtime_sec, 600),
        )
        self._run_checked(
            [
                str(python_bin),
                "-m",
                "pip",
                "install",
                "meson-python",
                "Cython",
                "ninja",
                "pytest",
            ],
            cwd=artifacts_dir,
            timeout_sec=min(self.config.max_runtime_sec, 900),
        )
        return python_bin

    def _install_numpy(self, python_bin: Path, worktree: Path) -> None:
        self._run_checked(
            [str(python_bin), "-m", "pip", "install", "--force-reinstall", "--no-build-isolation", "."],
            cwd=worktree,
            timeout_sec=min(self.config.max_runtime_sec, 1200),
        )

    def _run_oracle(self, python_bin: Path, worktree: Path, output_path: Path) -> dict[str, Any]:
        self._install_numpy(python_bin, worktree)

        oracle_script = (
            "import json\n"
            "import numpy as np\n"
            "\n"
            "def _message(a, b):\n"
            "    try:\n"
            "        np.convolve(a, b)\n"
            "        return None\n"
            "    except Exception as exc:\n"
            "        return str(exc)\n"
            "\n"
            "first = _message(np.array([]), np.array([1, 2]))\n"
            "second = _message(np.array([1, 2]), np.array([]))\n"
            "print(json.dumps({'first_error': first, 'second_error': second}, sort_keys=True))\n"
        )

        output = self.command_runner.run(
            [str(python_bin), "-c", oracle_script],
            cwd=worktree,
            timeout_sec=min(self.config.max_runtime_sec, 300),
        )
        payload: dict[str, Any] = {
            "returncode": output.returncode,
            "stdout": output.stdout,
            "stderr": output.stderr,
            "first_error": None,
            "second_error": None,
        }
        if output.returncode == 0:
            stdout = output.stdout.strip()
            try:
                parsed = json.loads(stdout)
                payload["first_error"] = parsed.get("first_error")
                payload["second_error"] = parsed.get("second_error")
            except json.JSONDecodeError:
                payload["parse_error"] = "oracle output was not valid JSON"
        self._write_json(output_path, payload)
        return payload

    def _run_codex_fix(self, candidate_worktree: Path, output_path: Path) -> CommandOutput:
        prompt = (
            "You are fixing numpy/numpy issue #30272. "
            "Modify only what is needed for this bug. "
            "Keep the patch minimal and behavior-preserving except for the bug fix. "
            "Bug: numpy.convolve reports the wrong empty-input error because argument swapping happens before empty checks. "
            "Fix it so empty input errors are reported for the correct argument. "
            "Do not change unrelated files."
        )
        result = self.command_runner.run(
            [
                "codex",
                "exec",
                prompt,
                "-s",
                "workspace-write",
                "--skip-git-repo-check",
                "-C",
                str(candidate_worktree),
                "-o",
                str(output_path),
            ],
            cwd=candidate_worktree,
            timeout_sec=self.config.max_runtime_sec,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "codex fix step failed")
        return result

    def _capture_candidate_diff(self, candidate_worktree: Path, patch_path: Path) -> str:
        diff_output = self.command_runner.run(
            ["git", "-C", str(candidate_worktree), "diff"],
            cwd=candidate_worktree,
        )
        if diff_output.returncode != 0:
            raise RuntimeError(diff_output.stderr or diff_output.stdout or "failed to get candidate diff")
        patch_path.write_text(diff_output.stdout, encoding="utf-8")
        return diff_output.stdout

    def _validate_candidate_patch(self, candidate_worktree: Path, diff_text: str) -> tuple[bool, str | None]:
        if not diff_text.strip():
            return False, "candidate patch is empty"

        names_output = self.command_runner.run(
            ["git", "-C", str(candidate_worktree), "diff", "--name-only"],
            cwd=candidate_worktree,
        )
        if names_output.returncode != 0:
            return False, names_output.stderr or names_output.stdout or "failed to inspect candidate patch files"

        changed = {line.strip() for line in names_output.stdout.splitlines() if line.strip()}
        if "numpy/_core/numeric.py" not in changed:
            return False, "candidate patch does not touch numpy/_core/numeric.py"
        return True, None

    def _classify_before_oracle(self, payload: dict[str, Any]) -> BeforeOracleState:
        first = str(payload.get("first_error") or "")
        if "v cannot be empty" in first:
            return "bug_present"
        return "unexpected"

    def _classify_after_oracle(self, payload: dict[str, Any]) -> AfterOracleState:
        first = str(payload.get("first_error") or "")
        second = str(payload.get("second_error") or "")
        if "a cannot be empty" in first and "v cannot be empty" in second:
            return "fixed"
        return "not_fixed"

    def _run_checked(self, args: list[str], cwd: Path, timeout_sec: int) -> None:
        output = self.command_runner.run(args, cwd=cwd, timeout_sec=timeout_sec)
        if output.returncode != 0:
            raise RuntimeError(output.stderr or output.stdout or f"command failed: {' '.join(args)}")

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = NumpyConvolveEvaluator._normalize_for_json(payload)
        path.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def _normalize_for_json(value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, list):
            return [NumpyConvolveEvaluator._normalize_for_json(item) for item in value]
        if isinstance(value, tuple):
            return [NumpyConvolveEvaluator._normalize_for_json(item) for item in value]
        if isinstance(value, dict):
            return {key: NumpyConvolveEvaluator._normalize_for_json(item) for key, item in value.items()}
        return value


def run_numpy_convolve_eval(
    config: NumpyConvolveEvalConfig,
    command_runner: CommandRunner | None = None,
) -> NumpyConvolveEvalResult:
    evaluator = NumpyConvolveEvaluator(config=config, command_runner=command_runner)
    return evaluator.run()
