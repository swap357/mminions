from __future__ import annotations

import unittest

from orchestrator.issue import IssueParseError, extract_failure_signals, normalize_issue_spec, parse_issue_url


class IssueTests(unittest.TestCase):
    def test_parse_issue_url(self) -> None:
        owner, repo, number = parse_issue_url("https://github.com/python/cpython/issues/12345")
        self.assertEqual(owner, "python")
        self.assertEqual(repo, "cpython")
        self.assertEqual(number, 12345)

    def test_parse_issue_url_invalid(self) -> None:
        with self.assertRaises(IssueParseError):
            parse_issue_url("https://example.com/issues/12")

    def test_extract_failure_signals(self) -> None:
        text = "ZeroDivisionError: division by zero. error: 'boom'. exit code 1"
        signals = extract_failure_signals(text)
        exception_types = {signal.exception_type for signal in signals}
        exit_codes = {signal.exit_code for signal in signals}
        self.assertIn("ZeroDivisionError", exception_types)
        self.assertIn(1, exit_codes)

    def test_normalize_issue_needs_human_without_signals(self) -> None:
        payload = {
            "title": "cleanup refactor",
            "body": "please refactor module",
            "labels": [{"name": "maintenance"}],
        }
        spec = normalize_issue_spec("https://github.com/org/repo/issues/1", payload)
        self.assertEqual(spec.status, "needs-human")
        self.assertIsNotNone(spec.needs_human_reason)


if __name__ == "__main__":
    unittest.main()
