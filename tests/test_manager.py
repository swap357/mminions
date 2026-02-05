from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
