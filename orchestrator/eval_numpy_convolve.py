from __future__ import annotations

from pathlib import Path
import argparse
import json

from orchestrator.evals.numpy_convolve import NumpyConvolveEvalConfig, run_numpy_convolve_eval
from orchestrator.types import dataclass_to_primitive


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run NumPy convolve before/after bug-fix eval")
    parser.add_argument("--mode", choices=["offline", "live"], required=True)
    parser.add_argument("--numpy-repo-path", required=True)
    parser.add_argument("--runs-root", required=True)
    parser.add_argument("--issue-url", default="https://github.com/numpy/numpy/issues/30272")
    parser.add_argument("--bug-commit", default="9f0519e83247b8a1b46c12fb583d4d575d992bd7")
    parser.add_argument("--reference-fix-commit", default="3a811fb9af105372da2d07d83e77ae085d51f54e")
    parser.add_argument("--python-version", default="3.12")
    parser.add_argument("--max-runtime-sec", type=int, default=900)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    config = NumpyConvolveEvalConfig(
        numpy_repo_path=Path(args.numpy_repo_path).resolve(),
        runs_root=Path(args.runs_root).resolve(),
        issue_url=args.issue_url,
        bug_commit=args.bug_commit,
        reference_fix_commit=args.reference_fix_commit,
        mode=args.mode,
        python_version=args.python_version,
        max_runtime_sec=max(60, args.max_runtime_sec),
    )

    result = run_numpy_convolve_eval(config)
    print(json.dumps(dataclass_to_primitive(result), indent=2, sort_keys=True, default=str))
    if result.status == "passed":
        return 0
    if result.status == "skipped":
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
