from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from orchestrator.workers import build_codex_exec_script


class WorkerScriptTests(unittest.TestCase):
    def test_build_script_includes_model_when_provided(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script_path = root / "worker.sh"
            output_path = root / "out.json"
            worktree = root / "wt"
            worktree.mkdir(parents=True, exist_ok=True)

            build_codex_exec_script(
                prompt="hello",
                output_path=output_path,
                script_path=script_path,
                worktree_path=worktree,
                model="fast-model",
            )

            script = script_path.read_text(encoding="utf-8")
            self.assertIn("-m fast-model", script)

    def test_build_script_includes_json_telemetry_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script_path = root / "worker.sh"
            output_path = root / "out.json"
            telemetry_path = root / "worker.jsonl"
            worktree = root / "wt"
            worktree.mkdir(parents=True, exist_ok=True)

            build_codex_exec_script(
                prompt="hello",
                output_path=output_path,
                script_path=script_path,
                worktree_path=worktree,
                telemetry_path=telemetry_path,
            )

            script = script_path.read_text(encoding="utf-8")
            self.assertIn("--json > \"$TELEMETRY_FILE\"", script)
            self.assertIn(f"TELEMETRY_FILE={telemetry_path}", script)


if __name__ == "__main__":
    unittest.main()
