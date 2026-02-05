from __future__ import annotations

from pathlib import Path
import os
import subprocess
import unittest

try:
    import pytest
except Exception:  # pragma: no cover - allows unittest discovery without pytest installed
    class _PytestStub:
        class mark:
            @staticmethod
            def live_eval(func):
                return func

        @staticmethod
        def skip(reason: str) -> None:
            raise unittest.SkipTest(reason)

    pytest = _PytestStub()  # type: ignore[assignment]

from orchestrator.command import CommandOutput
from orchestrator.evals.numpy_convolve import NumpyConvolveEvalConfig, run_numpy_convolve_eval


def _run(args: list[str], cwd: Path) -> None:
    completed = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(args)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )


def _make_repo(root: Path) -> tuple[Path, str]:
    repo = root / "repo"
    (repo / "numpy" / "_core").mkdir(parents=True)
    (repo / "numpy" / "_core" / "numeric.py").write_text("def sentinel():\n    return 1\n", encoding="utf-8")
    (repo / "README.md").write_text("test repo\n", encoding="utf-8")

    _run(["git", "init"], cwd=repo)
    _run(["git", "config", "user.name", "test"], cwd=repo)
    _run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "init"], cwd=repo)

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo), text=True).strip()
    return repo, commit


def test_live_skips_when_codex_auth_unavailable(tmp_path: Path, monkeypatch) -> None:
    repo, commit = _make_repo(tmp_path)

    config = NumpyConvolveEvalConfig(
        numpy_repo_path=repo,
        runs_root=tmp_path / "runs",
        bug_commit=commit,
        reference_fix_commit=commit,
        mode="live",
    )

    from orchestrator.evals import numpy_convolve

    monkeypatch.setattr(
        numpy_convolve.NumpyConvolveEvaluator,
        "_check_codex_auth",
        lambda self, worktree: (False, "codex auth unavailable"),
    )

    result = run_numpy_convolve_eval(config)

    assert result.status == "skipped"
    assert result.skip_reason == "codex auth unavailable"
    assert result.codex_invoked is False


def test_live_fails_when_candidate_patch_empty(tmp_path: Path, monkeypatch) -> None:
    repo, commit = _make_repo(tmp_path)

    config = NumpyConvolveEvalConfig(
        numpy_repo_path=repo,
        runs_root=tmp_path / "runs",
        bug_commit=commit,
        reference_fix_commit=commit,
        mode="live",
    )

    from orchestrator.evals import numpy_convolve

    monkeypatch.setattr(numpy_convolve.NumpyConvolveEvaluator, "_check_codex_auth", lambda self, worktree: (True, "ok"))
    monkeypatch.setattr(numpy_convolve.NumpyConvolveEvaluator, "_bootstrap_runtime", lambda self, artifacts: Path("/usr/bin/python3"))

    def _fake_oracle(self, python_bin: Path, worktree: Path, output_path: Path):
        payload = {"first_error": "v cannot be empty", "second_error": "v cannot be empty"}
        output_path.write_text('{"first_error":"v cannot be empty","second_error":"v cannot be empty"}\n', encoding="utf-8")
        return payload

    monkeypatch.setattr(numpy_convolve.NumpyConvolveEvaluator, "_run_oracle", _fake_oracle)

    def _fake_codex(self, candidate_worktree: Path, output_path: Path) -> CommandOutput:
        output_path.write_text("no changes\n", encoding="utf-8")
        return CommandOutput(args=("codex",), cwd=str(candidate_worktree), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(numpy_convolve.NumpyConvolveEvaluator, "_run_codex_fix", _fake_codex)

    result = run_numpy_convolve_eval(config)

    assert result.status == "failed"
    assert result.before_oracle == "bug_present"
    assert result.after_oracle == "not_run"
    assert result.codex_invoked is True
    validation = (result.artifacts_dir / "candidate_patch_validation.json").read_text(encoding="utf-8")
    assert "candidate patch is empty" in validation


def test_live_fails_when_patch_does_not_touch_numeric(tmp_path: Path, monkeypatch) -> None:
    repo, commit = _make_repo(tmp_path)

    config = NumpyConvolveEvalConfig(
        numpy_repo_path=repo,
        runs_root=tmp_path / "runs",
        bug_commit=commit,
        reference_fix_commit=commit,
        mode="live",
    )

    from orchestrator.evals import numpy_convolve

    monkeypatch.setattr(numpy_convolve.NumpyConvolveEvaluator, "_check_codex_auth", lambda self, worktree: (True, "ok"))
    monkeypatch.setattr(numpy_convolve.NumpyConvolveEvaluator, "_bootstrap_runtime", lambda self, artifacts: Path("/usr/bin/python3"))

    def _fake_oracle(self, python_bin: Path, worktree: Path, output_path: Path):
        payload = {"first_error": "v cannot be empty", "second_error": "v cannot be empty"}
        output_path.write_text('{"first_error":"v cannot be empty","second_error":"v cannot be empty"}\n', encoding="utf-8")
        return payload

    monkeypatch.setattr(numpy_convolve.NumpyConvolveEvaluator, "_run_oracle", _fake_oracle)

    def _fake_codex(self, candidate_worktree: Path, output_path: Path) -> CommandOutput:
        readme = candidate_worktree / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "edited\n", encoding="utf-8")
        output_path.write_text("updated README\n", encoding="utf-8")
        return CommandOutput(args=("codex",), cwd=str(candidate_worktree), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(numpy_convolve.NumpyConvolveEvaluator, "_run_codex_fix", _fake_codex)

    result = run_numpy_convolve_eval(config)

    assert result.status == "failed"
    validation = (result.artifacts_dir / "candidate_patch_validation.json").read_text(encoding="utf-8")
    assert "does not touch numpy/_core/numeric.py" in validation


@pytest.mark.live_eval
def test_live_end_to_end_optional(tmp_path: Path) -> None:
    if os.getenv("MMINIONS_RUN_LIVE_EVAL") != "1":
        pytest.skip("set MMINIONS_RUN_LIVE_EVAL=1 to run live eval")

    default_repo = "/Users/mac357/Documents/mminions/projects/numpy"
    repo = Path(os.getenv("MMINIONS_NUMPY_REPO", default_repo)).resolve()
    if not repo.exists():
        pytest.skip(f"numpy repo not found: {repo}")

    config = NumpyConvolveEvalConfig(
        numpy_repo_path=repo,
        runs_root=tmp_path / "runs",
        mode="live",
        max_runtime_sec=1800,
    )

    result = run_numpy_convolve_eval(config)

    assert result.status in {"passed", "skipped"}
    if result.status == "skipped":
        assert result.skip_reason
    assert (result.artifacts_dir / "summary.json").exists()
