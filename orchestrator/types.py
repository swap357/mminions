from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


UTC_ISO = "%Y-%m-%dT%H:%M:%SZ"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime(UTC_ISO)


@dataclass(frozen=True)
class FailureSignal:
    exception_type: str | None = None
    message_substring: str | None = None
    exit_code: int | None = None
    raw_pattern: str | None = None


@dataclass(frozen=True)
class IssueSpec:
    issue_url: str
    repo_slug: str
    issue_number: int
    title: str
    body: str
    labels: list[str] = field(default_factory=list)
    expected_failure_signals: list[FailureSignal] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    target_paths: list[str] = field(default_factory=list)
    status: str = "ok"
    needs_human_reason: str | None = None


@dataclass(frozen=True)
class WorkerTask:
    run_id: str
    role: str
    worker_id: str
    input_payload_path: str
    output_path: str
    worktree_path: str


@dataclass(frozen=True)
class WorkerResult:
    worker_id: str
    role: str
    status: str
    output_path: str
    started_at: str
    finished_at: str
    session_name: str
    exit_code: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    total_runs: int
    matches: int
    matched_signature: str
    passed: bool


@dataclass(frozen=True)
class ReproCandidate:
    candidate_id: str
    worker_id: str
    script: str
    setup_commands: list[str]
    oracle_command: str
    claimed_failure_signature: str
    file_extension: str = "py"
    validation: ValidationResult | None = None
    score: float | None = None


@dataclass(frozen=True)
class TriageEvidence:
    file: str
    line: int
    snippet: str


@dataclass(frozen=True)
class TriageHypothesis:
    hypothesis_id: str
    mechanism: str
    evidence: list[TriageEvidence]
    confidence: float
    disconfirming_checks: list[str]
    worker_id: str
    score: float | None = None


@dataclass(frozen=True)
class RunDecision:
    status: str
    selected_repro_candidate_id: str | None
    rationale: str
    top_hypotheses: list[str]
    next_fix_targets: list[str]
    diagnostics: list[str]
    created_at: str = field(default_factory=now_utc_iso)


def dataclass_to_json_file(value: Any, path: Path) -> None:
    payload = dataclass_to_primitive(value)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def dataclass_to_primitive(value: Any) -> Any:
    if isinstance(value, list):
        return [dataclass_to_primitive(item) for item in value]
    if isinstance(value, tuple):
        return [dataclass_to_primitive(item) for item in value]
    if isinstance(value, dict):
        return {k: dataclass_to_primitive(v) for k, v in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return {k: dataclass_to_primitive(v) for k, v in asdict(value).items()}
    return value


def json_file_to_dict(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
