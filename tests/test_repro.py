from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from orchestrator.repro import choose_best_candidate, minimize_candidate, parse_repro_candidate, validate_candidate
from orchestrator.types import FailureSignal, IssueSpec, ReproCandidate, ValidationResult


class FakeCommandRunner:
    def __init__(self) -> None:
        self.oracle_calls = 0

    def run(self, args, cwd, timeout_sec=None, check=False):
        class Output:
            def __init__(self):
                self.returncode = 1
                self.stdout = ""
                self.stderr = "codex unavailable in unit test"

        return Output()

    def run_shell(self, command, cwd, timeout_sec=None, check=False):
        self.oracle_calls += 1

        class Output:
            def __init__(self, stdout: str, stderr: str, returncode: int):
                self.stdout = stdout
                self.stderr = stderr
                self.returncode = returncode

        if "setup" in command:
            return Output("", "", 0)

        parts = command.split()
        repro_path = Path(parts[-1]) if parts else None
        script_text = repro_path.read_text(encoding="utf-8") if repro_path and repro_path.exists() else ""

        if "ESSENTIAL" in script_text:
            return Output("ZeroDivisionError", "", 1)
        return Output("", "no failure", 0)


class ReproTests(unittest.TestCase):
    def test_parse_candidate_with_wrapped_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out = Path(temp_dir) / "w1.json"
            out.write_text(
                "result:\\n```json\\n"
                "{\"candidate_id\":\"w1-candidate\",\"script\":\"print(1)\","
                "\"setup_commands\":[],\"oracle_command\":\"python {repro_file}\","
                "\"claimed_failure_signature\":\"ZeroDivisionError\",\"file_extension\":\"py\"}"
                "\\n```\\n",
                encoding="utf-8",
            )
            candidate = parse_repro_candidate("w1", out)

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.candidate_id, "w1-candidate")

    def test_validate_candidate_passes_deterministic_gate(self) -> None:
        issue_spec = IssueSpec(
            issue_url="https://github.com/org/repo/issues/1",
            repo_slug="org/repo",
            issue_number=1,
            title="ZeroDivisionError in parser",
            body="",
            expected_failure_signals=[FailureSignal(exception_type="ZeroDivisionError")],
        )
        candidate = ReproCandidate(
            candidate_id="w1-candidate",
            worker_id="w1",
            script="print('ESSENTIAL')\n",
            setup_commands=[],
            oracle_command="python {repro_file}",
            claimed_failure_signature="ZeroDivisionError",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            runner = FakeCommandRunner()
            result = validate_candidate(
                candidate=candidate,
                issue_spec=issue_spec,
                repo_path=Path(temp_dir),
                candidate_script_path=Path(temp_dir) / "cand.py",
                command_runner=runner,
                runs=5,
                timeout_sec=5,
            )

        self.assertTrue(result.passed)
        self.assertEqual(result.matches, 5)

    def test_choose_best_candidate(self) -> None:
        issue_spec = IssueSpec(
            issue_url="https://github.com/org/repo/issues/1",
            repo_slug="org/repo",
            issue_number=1,
            title="ZeroDivisionError in parser",
            body="",
            expected_failure_signals=[FailureSignal(exception_type="ZeroDivisionError")],
        )
        c1 = ReproCandidate(
            candidate_id="c1",
            worker_id="w1",
            script="line\n",
            setup_commands=[],
            oracle_command="cmd",
            claimed_failure_signature="ZeroDivisionError",
            validation=ValidationResult(total_runs=5, matches=5, matched_signature="ZeroDivisionError", passed=True),
        )
        c2 = ReproCandidate(
            candidate_id="c2",
            worker_id="w2",
            script="line\nline\nline\n",
            setup_commands=[],
            oracle_command="cmd",
            claimed_failure_signature="other",
            validation=ValidationResult(total_runs=5, matches=4, matched_signature="other", passed=True),
        )

        best = choose_best_candidate([c2, c1], issue_spec)
        self.assertIsNotNone(best)
        self.assertEqual(best.candidate_id, "c1")

    def test_minimize_candidate_keeps_essential_line(self) -> None:
        issue_spec = IssueSpec(
            issue_url="https://github.com/org/repo/issues/1",
            repo_slug="org/repo",
            issue_number=1,
            title="ZeroDivisionError in parser",
            body="",
            expected_failure_signals=[FailureSignal(exception_type="ZeroDivisionError")],
        )
        candidate = ReproCandidate(
            candidate_id="c1",
            worker_id="w1",
            script="noise1\nESSENTIAL\nnoise2\n",
            setup_commands=[],
            oracle_command="python {repro_file}",
            claimed_failure_signature="ZeroDivisionError",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runner = FakeCommandRunner()
            minimized = minimize_candidate(
                candidate=candidate,
                issue_spec=issue_spec,
                repo_path=root,
                command_runner=runner,
                semantic_output_path=root / "semantic.txt",
                minimal_output_path=root / "minimal.py",
                timeout_sec=5,
            )

        self.assertIn("ESSENTIAL", minimized.script)
        self.assertTrue(minimized.validation and minimized.validation.passed)


if __name__ == "__main__":
    unittest.main()
