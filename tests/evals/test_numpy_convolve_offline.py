from __future__ import annotations

from pathlib import Path
import json
import subprocess

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


def test_offline_creates_artifacts_and_summary(tmp_path: Path) -> None:
    repo, commit = _make_repo(tmp_path)
    runs_root = tmp_path / "runs"

    config = NumpyConvolveEvalConfig(
        numpy_repo_path=repo,
        runs_root=runs_root,
        bug_commit=commit,
        reference_fix_commit=commit,
        mode="offline",
    )

    result = run_numpy_convolve_eval(config)

    assert result.status == "passed"
    assert result.before_oracle == "bug_present"
    assert result.after_oracle == "not_run"
    assert result.artifacts_dir.exists()

    summary = json.loads((result.artifacts_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "passed"
    assert Path(summary["artifacts_dir"]) == result.artifacts_dir

    assert (result.artifacts_dir / "before_oracle.json").exists()
    assert not (result.artifacts_dir / "worktrees" / "before").exists()
    assert not (result.artifacts_dir / "worktrees" / "candidate").exists()


def test_offline_failure_still_cleans_up_worktrees(tmp_path: Path, monkeypatch) -> None:
    repo, commit = _make_repo(tmp_path)
    runs_root = tmp_path / "runs"

    config = NumpyConvolveEvalConfig(
        numpy_repo_path=repo,
        runs_root=runs_root,
        bug_commit=commit,
        reference_fix_commit=commit,
        mode="offline",
    )

    from orchestrator.evals import numpy_convolve

    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(numpy_convolve.NumpyConvolveEvaluator, "_offline_before_oracle", _raise)

    result = run_numpy_convolve_eval(config)

    assert result.status == "failed"
    assert (result.artifacts_dir / "error.json").exists()
    assert not (result.artifacts_dir / "worktrees" / "before").exists()
    assert not (result.artifacts_dir / "worktrees" / "candidate").exists()


def test_offline_artifacts_are_unique(tmp_path: Path) -> None:
    repo, commit = _make_repo(tmp_path)
    runs_root = tmp_path / "runs"

    config = NumpyConvolveEvalConfig(
        numpy_repo_path=repo,
        runs_root=runs_root,
        bug_commit=commit,
        reference_fix_commit=commit,
        mode="offline",
    )

    result_a = run_numpy_convolve_eval(config)
    result_b = run_numpy_convolve_eval(config)

    assert result_a.artifacts_dir != result_b.artifacts_dir
    assert result_a.artifacts_dir.exists()
    assert result_b.artifacts_dir.exists()
