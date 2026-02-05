from __future__ import annotations

from pathlib import Path
import unittest

from orchestrator.manager import Manager
from orchestrator.types import TriageEvidence, TriageHypothesis


class ManagerTests(unittest.TestCase):
    def test_triage_disagreement_high_when_scores_close(self) -> None:
        hypotheses = [
            TriageHypothesis(
                hypothesis_id="h1",
                mechanism="path A",
                evidence=[TriageEvidence(file="a.py", line=1, snippet="x")],
                confidence=0.8,
                disconfirming_checks=[],
                worker_id="w1",
                score=0.7,
            ),
            TriageHypothesis(
                hypothesis_id="h2",
                mechanism="path B",
                evidence=[TriageEvidence(file="b.py", line=1, snippet="y")],
                confidence=0.8,
                disconfirming_checks=[],
                worker_id="w2",
                score=0.62,
            ),
        ]
        self.assertTrue(Manager._triage_disagreement_high(hypotheses))

    def test_triage_disagreement_low_when_single_mechanism(self) -> None:
        hypotheses = [
            TriageHypothesis(
                hypothesis_id="h1",
                mechanism="same path",
                evidence=[TriageEvidence(file="a.py", line=1, snippet="x")],
                confidence=0.8,
                disconfirming_checks=[],
                worker_id="w1",
                score=0.7,
            ),
            TriageHypothesis(
                hypothesis_id="h2",
                mechanism="same path",
                evidence=[TriageEvidence(file="a.py", line=2, snippet="z")],
                confidence=0.7,
                disconfirming_checks=[],
                worker_id="w2",
                score=0.6,
            ),
        ]
        self.assertFalse(Manager._triage_disagreement_high(hypotheses))

    def test_format_human_summary_includes_metrics_and_tokens(self) -> None:
        payload = {
            "status": "ok",
            "selected_repro_candidate_id": "w1-candidate",
            "rationale": "deterministic repro found",
            "top_hypotheses": ["mechanism a"],
            "next_fix_targets": ["numpy/_core/numeric.py:1"],
            "diagnostics": [],
            "metrics": {
                "timing_sec": {"preflight": 1.25, "total": 9.5},
                "tokens": {
                    "workers": {"input_tokens": 10, "cached_input_tokens": 3, "output_tokens": 4, "turns": 2},
                    "manager": {"input_tokens": 5, "cached_input_tokens": 2, "output_tokens": 1, "turns": 1},
                    "total": {"input_tokens": 15, "cached_input_tokens": 5, "output_tokens": 5, "turns": 3},
                },
            },
        }
        rendered = Manager.format_human_summary(
            payload=payload,
            run_id="run-1",
            issue_url="https://github.com/numpy/numpy/issues/30272",
            run_dir=Path("/tmp/runs/run-1"),
        )
        self.assertIn("mminions manager result", rendered)
        self.assertIn("status: ok", rendered)
        self.assertIn("timing:", rendered)
        self.assertIn("- preflight: 1.250s", rendered)
        self.assertIn("- total: 9.500s", rendered)
        self.assertIn("workers: input=10 cached=3 output=4 turns=2", rendered)
        self.assertIn("manager: input=5 cached=2 output=1 turns=1", rendered)
        self.assertIn("total: input=15 cached=5 output=5 turns=3", rendered)

    def test_format_human_summary_handles_missing_metrics(self) -> None:
        payload = {
            "status": "needs-human",
            "selected_repro_candidate_id": None,
            "rationale": "no candidate",
            "top_hypotheses": [],
            "next_fix_targets": [],
        }
        rendered = Manager.format_human_summary(
            payload=payload,
            run_id="run-2",
            issue_url="https://github.com/numpy/numpy/issues/30272",
            run_dir=Path("/tmp/runs/run-2"),
        )
        self.assertIn("status: needs-human", rendered)
        self.assertIn("top_hypotheses:", rendered)
        self.assertIn("1. none", rendered)
        self.assertIn("timing:", rendered)
        self.assertIn("- unavailable", rendered)
        self.assertIn("workers: input=0 cached=0 output=0 turns=0", rendered)


if __name__ == "__main__":
    unittest.main()
