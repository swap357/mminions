from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from orchestrator.triage import parse_triage_output, rank_hypotheses, top_hypotheses


class TriageTests(unittest.TestCase):
    def test_rank_filters_invalid_and_sorts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            src = root / "module.py"
            src.write_text("def boom():\n    raise ValueError('x')\n", encoding="utf-8")

            output = root / "triage.json"
            output.write_text(
                json.dumps(
                    {
                        "hypotheses": [
                            {
                                "hypothesis_id": "w1-h1",
                                "mechanism": "raises ValueError due to invalid branch",
                                "evidence": [{"file": "module.py", "line": 2, "snippet": "raise ValueError"}],
                                "confidence": 0.9,
                                "disconfirming_checks": ["input sanitization test"],
                            },
                            {
                                "hypothesis_id": "w1-h2",
                                "mechanism": "",
                                "evidence": [{"file": "missing.py", "line": 1, "snippet": "x"}],
                                "confidence": 0.1,
                                "disconfirming_checks": [],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            parsed = parse_triage_output("w1", output)
            ranked = rank_hypotheses(root, parsed, repro_text="ValueError path")
            top = top_hypotheses(ranked, limit=1)

            self.assertEqual(len(ranked), 1)
            self.assertEqual(top[0].hypothesis_id, "w1-h1")
            self.assertGreater((top[0].score or 0.0), 0.0)

    def test_parse_triage_output_from_wrapped_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = root / "triage.json"
            output.write_text(
                "analysis\\n```json\\n"
                "{\"hypotheses\":[{\"hypothesis_id\":\"w2-h1\",\"mechanism\":\"x\","
                "\"evidence\":[{\"file\":\"a.py\",\"line\":1,\"snippet\":\"x\"}],"
                "\"confidence\":0.2,\"disconfirming_checks\":[]}]}\\n```\\n",
                encoding="utf-8",
            )
            parsed = parse_triage_output("w2", output)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(parsed[0].hypothesis_id, "w2-h1")


if __name__ == "__main__":
    unittest.main()
