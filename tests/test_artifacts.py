from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from orchestrator.artifacts import ArtifactStore


class ArtifactTests(unittest.TestCase):
    def test_contract_files_created(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ArtifactStore(Path(temp_dir), "run-1")
            paths = store.initialize_contract()

            self.assertTrue(paths.issue_json.exists())
            self.assertTrue(paths.sessions_json.exists())
            self.assertTrue(paths.repro_candidates_dir.exists())
            self.assertTrue((paths.repro_dir / "minimal_repro.txt").exists())
            self.assertTrue(paths.triage_hypotheses_json.exists())
            self.assertTrue(paths.decision_json.exists())
            self.assertTrue(paths.final_md.exists())


if __name__ == "__main__":
    unittest.main()
