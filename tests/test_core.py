from pathlib import Path
import tempfile

from mminions.config import load_config, Config
from mminions.issue import parse_issue_url, IssueParseError
from mminions.types import IssueSpec, ReproCandidate, Hypothesis, RunResult
from mminions.workers import repro_prompt, triage_prompt


def test_parse_issue_url():
    owner, repo, num = parse_issue_url("https://github.com/numpy/numpy/issues/30272")
    assert owner == "numpy"
    assert repo == "numpy"
    assert num == 30272


def test_parse_issue_url_invalid():
    try:
        parse_issue_url("https://example.com/issues/1")
        assert False
    except IssueParseError:
        pass


def test_load_config_defaults():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = load_config(Path(tmp) / "nonexistent.toml")
        assert cfg.workers == 2
        assert cfg.timeout_sec == 300


def test_repro_prompt():
    issue = IssueSpec("url", "owner", "repo", 1, "title", "body")
    prompt = repro_prompt(issue, "w1")
    assert "owner/repo#1" in prompt
    assert "title" in prompt


def test_triage_prompt():
    issue = IssueSpec("url", "owner", "repo", 1, "title", "body")
    prompt = triage_prompt(issue, "w1", "print(1)")
    assert "print(1)" in prompt


def test_run_result():
    result = RunResult("run-1", "ok", None, [])
    assert result.run_id == "run-1"
    assert result.status == "ok"
