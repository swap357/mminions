from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class IssueSpec:
    url: str
    owner: str
    repo: str
    number: int
    title: str
    body: str


@dataclass(frozen=True)
class ReproCandidate:
    worker_id: str
    script: str
    oracle_command: str
    failure_signature: str


@dataclass(frozen=True)
class Hypothesis:
    worker_id: str
    mechanism: str
    file: str
    line: int


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    repro: ReproCandidate | None
    hypotheses: list[Hypothesis]
    created_at: str = field(default_factory=now_utc)


def to_dict(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {k: to_dict(v) for k, v in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return {k: to_dict(v) for k, v in asdict(value).items()}
    return value
