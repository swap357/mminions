from __future__ import annotations

from pathlib import Path
import json
import shlex

from .types import IssueSpec


def repro_prompt(issue: IssueSpec, worker_id: str) -> str:
    return f"""Build a minimal reproducer for this GitHub issue.
Output JSON only:
{{
  "script": "<python script>",
  "oracle_command": "python {{repro_file}}",
  "failure_signature": "<string that appears when bug reproduces>"
}}

Issue: {issue.owner}/{issue.repo}#{issue.number}
Title: {issue.title}

{issue.body}
"""


def triage_prompt(issue: IssueSpec, worker_id: str, repro_script: str) -> str:
    return f"""Analyze this bug and find the root cause in the codebase.
Output JSON only:
{{
  "hypotheses": [
    {{"mechanism": "<what fails and why>", "file": "<path>", "line": <number>}}
  ]
}}

Issue: {issue.owner}/{issue.repo}#{issue.number}
Title: {issue.title}

Reproducer:
```python
{repro_script}
```

{issue.body}
"""


def make_worker_script(prompt: str, output_path: Path, worktree: Path, model: str = "") -> str:
    model_arg = f"-m {shlex.quote(model)} " if model else ""
    escaped_prompt = shlex.quote(prompt)
    return f"""#!/usr/bin/env bash
set -euo pipefail
cd {worktree}
codex exec {escaped_prompt} {model_arg}-s read-only -C {worktree} -o {output_path}
"""
