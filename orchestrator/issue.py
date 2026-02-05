from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import os
import re

from .types import FailureSignal, IssueSpec


ISSUE_URL_RE = re.compile(r"^https?://github\.com/([\w.-]+)/([\w.-]+)/issues/(\d+)(?:[/?#].*)?$")

EXCEPTION_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Failure|AssertionError))\b")
ASSERT_RE = re.compile(r"\b(assert(?:ion)?\s+failed|assert\b)\b", re.IGNORECASE)
PATH_RE = re.compile(r"\b([A-Za-z0-9_./-]+\.(?:py|c|cc|cpp|h|hpp|js|ts|go|rs|java|rb|swift))\b")
MESSAGE_RE = re.compile(r"(?:message|error|exception)[:\s]+[`'\"]([^`'\"]{3,200})[`'\"]", re.IGNORECASE)
CONSTRAINT_RE = re.compile(r"\b(must|cannot|can't|should|do not|don't|required|requirement)\b", re.IGNORECASE)
EXIT_CODE_RE = re.compile(r"(?:exit(?:\s+code)?|returns?)\s*[:=]?\s*(-?\d+)", re.IGNORECASE)


class IssueParseError(ValueError):
    pass


def parse_issue_url(issue_url: str) -> tuple[str, str, int]:
    match = ISSUE_URL_RE.match(issue_url.strip())
    if not match:
        raise IssueParseError(f"invalid GitHub issue URL: {issue_url}")
    owner, repo, number = match.group(1), match.group(2), int(match.group(3))
    return owner, repo, number


def _github_api_url(owner: str, repo: str, number: int) -> str:
    return f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"


def fetch_issue_json(issue_url: str) -> dict[str, Any]:
    owner, repo, number = parse_issue_url(issue_url)
    api_url = _github_api_url(owner, repo, number)

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "mminions-orchestrator",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(api_url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise IssueParseError(f"github API request failed ({exc.code}): {body}") from exc
    except URLError as exc:
        raise IssueParseError(f"github API request failed: {exc.reason}") from exc


def extract_failure_signals(text: str) -> list[FailureSignal]:
    signals: list[FailureSignal] = []
    seen: set[tuple[str | None, str | None, int | None, str | None]] = set()

    for exception_type in EXCEPTION_RE.findall(text):
        signal = FailureSignal(exception_type=exception_type)
        key = (signal.exception_type, signal.message_substring, signal.exit_code, signal.raw_pattern)
        if key not in seen:
            seen.add(key)
            signals.append(signal)

    if ASSERT_RE.search(text):
        signal = FailureSignal(exception_type="AssertionError", raw_pattern="assert")
        key = (signal.exception_type, signal.message_substring, signal.exit_code, signal.raw_pattern)
        if key not in seen:
            seen.add(key)
            signals.append(signal)

    for message in MESSAGE_RE.findall(text):
        signal = FailureSignal(message_substring=message.strip())
        key = (signal.exception_type, signal.message_substring, signal.exit_code, signal.raw_pattern)
        if key not in seen:
            seen.add(key)
            signals.append(signal)

    for code in EXIT_CODE_RE.findall(text):
        signal = FailureSignal(exit_code=int(code))
        key = (signal.exception_type, signal.message_substring, signal.exit_code, signal.raw_pattern)
        if key not in seen:
            seen.add(key)
            signals.append(signal)

    return signals


def normalize_issue_spec(issue_url: str, payload: dict[str, Any]) -> IssueSpec:
    owner, repo, number = parse_issue_url(issue_url)
    title = str(payload.get("title") or "").strip()
    body = str(payload.get("body") or "").strip()
    labels = [label.get("name", "") for label in payload.get("labels", []) if isinstance(label, dict)]
    combined_text = f"{title}\n\n{body}"

    expected_failure_signals = extract_failure_signals(combined_text)
    constraints = sorted({line.strip() for line in body.splitlines() if CONSTRAINT_RE.search(line)})
    target_paths = sorted(set(PATH_RE.findall(combined_text)))

    status = "ok"
    needs_human_reason = None

    if not expected_failure_signals:
        status = "needs-human"
        needs_human_reason = "no structured failure signal found in issue title/body"

    return IssueSpec(
        issue_url=issue_url,
        repo_slug=f"{owner}/{repo}",
        issue_number=number,
        title=title,
        body=body,
        labels=labels,
        expected_failure_signals=expected_failure_signals,
        constraints=constraints,
        target_paths=target_paths,
        status=status,
        needs_human_reason=needs_human_reason,
    )


def write_issue_spec(issue_spec: IssueSpec, path: Path) -> None:
    payload = asdict(issue_spec)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
