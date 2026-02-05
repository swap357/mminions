from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import shlex

from .types import IssueSpec


ROLE_REPRO_BUILDER = "REPRO_BUILDER"
ROLE_TRIAGER = "TRIAGER"


@dataclass(frozen=True)
class WorkerCommand:
    role: str
    prompt: str
    output_path: Path
    session_script: Path


def _issue_spec_json(issue_spec: IssueSpec) -> str:
    payload = {
        "issue_url": issue_spec.issue_url,
        "repo_slug": issue_spec.repo_slug,
        "issue_number": issue_spec.issue_number,
        "title": issue_spec.title,
        "body": issue_spec.body,
        "labels": issue_spec.labels,
        "expected_failure_signals": [
            {
                "exception_type": signal.exception_type,
                "message_substring": signal.message_substring,
                "exit_code": signal.exit_code,
                "raw_pattern": signal.raw_pattern,
            }
            for signal in issue_spec.expected_failure_signals
        ],
        "constraints": issue_spec.constraints,
        "target_paths": issue_spec.target_paths,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def build_repro_prompt(issue_spec: IssueSpec, worker_id: str) -> str:
    return f"""ROLE: {ROLE_REPRO_BUILDER}
TASK: Build a minimal reproducer candidate for this GitHub issue.
OUTPUT FORMAT: JSON only, no markdown.

Required JSON schema:
{{
  "candidate_id": "{worker_id}-candidate",
  "script": "<full repro script text>",
  "setup_commands": ["<shell command>", "..."],
  "oracle_command": "<shell command; can reference {{repro_file}} placeholder>",
  "claimed_failure_signature": "<short string that must appear when bug reproduces>",
  "file_extension": "py"
}}

Constraints:
- Keep setup_commands minimal and deterministic.
- oracle_command must fail loudly if bug is not reproduced.
- preserve the issue's likely root cause behavior.
- Do not propose codebase edits.

Issue Spec:
{_issue_spec_json(issue_spec)}
"""


def build_triage_prompt(
    issue_spec: IssueSpec,
    worker_id: str,
    minimal_repro: str,
    code_search_hints: list[str],
) -> str:
    hints = "\n".join(f"- {hint}" for hint in code_search_hints) or "- none"
    return f"""ROLE: {ROLE_TRIAGER}
TASK: Produce triage hypotheses for the bug. Use repository evidence and minimal repro.
OUTPUT FORMAT: JSON only, no markdown.

Required JSON schema:
{{
  "hypotheses": [
    {{
      "hypothesis_id": "{worker_id}-h1",
      "mechanism": "<what fails and why>",
      "evidence": [{{"file": "path", "line": 123, "snippet": "code"}}],
      "confidence": 0.0,
      "disconfirming_checks": ["<check>"]
    }}
  ]
}}

Rules:
- confidence must be within [0, 1].
- include at least one evidence row per hypothesis.
- list concrete disconfirming checks.
- no fixes in this phase.

Code search hints:
{hints}

Minimal repro script:
```text
{minimal_repro}
```

Issue Spec:
{_issue_spec_json(issue_spec)}
"""


def build_codex_exec_script(
    prompt: str,
    output_path: Path,
    script_path: Path,
    worktree_path: Path,
    model: str = "",
    telemetry_path: Path | None = None,
) -> None:
    prompt_path = script_path.with_suffix(".prompt.txt")
    prompt_path.write_text(prompt, encoding="utf-8")
    model_arg = f"-m {shlex.quote(model)} " if model.strip() else ""
    telemetry_assign = ""
    telemetry_sink = ""
    if telemetry_path is not None:
        telemetry_assign = f"TELEMETRY_FILE={telemetry_path}\n"
        telemetry_sink = '--json > "$TELEMETRY_FILE"'
    script = f"""#!/usr/bin/env zsh
set -euo pipefail
PROMPT_FILE={prompt_path}
OUTPUT_FILE={output_path}
{telemetry_assign}
cd {worktree_path}
codex exec "$(cat \"$PROMPT_FILE\")" {model_arg}-s read-only --skip-git-repo-check -C {worktree_path} -o "$OUTPUT_FILE" {telemetry_sink}
"""
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(0o755)
