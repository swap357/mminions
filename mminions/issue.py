from __future__ import annotations

from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import os
import re

from .types import IssueSpec

ISSUE_URL_RE = re.compile(r"^https?://github\.com/([\w.-]+)/([\w.-]+)/issues/(\d+)")


class IssueParseError(ValueError):
    pass


def parse_issue_url(url: str) -> tuple[str, str, int]:
    match = ISSUE_URL_RE.match(url.strip())
    if not match:
        raise IssueParseError(f"invalid GitHub issue URL: {url}")
    return match.group(1), match.group(2), int(match.group(3))


def fetch_issue(url: str) -> IssueSpec:
    owner, repo, number = parse_issue_url(url)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"

    headers = {"Accept": "application/vnd.github+json", "User-Agent": "mminions"}
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"

    request = Request(api_url, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        raise IssueParseError(f"GitHub API failed: {exc}") from exc

    return IssueSpec(
        url=url,
        owner=owner,
        repo=repo,
        number=number,
        title=str(data.get("title") or ""),
        body=str(data.get("body") or ""),
    )
