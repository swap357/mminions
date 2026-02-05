from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from orchestrator.config import load_manager_defaults


class ConfigTests(unittest.TestCase):
    def test_load_defaults_without_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            defaults = load_manager_defaults(cwd=root)
            self.assertEqual(defaults.runs_root, (root / "runs").resolve())
            self.assertEqual(defaults.min_workers, 2)
            self.assertEqual(defaults.repro_min_matches, 1)
            self.assertEqual(defaults.validation_python_version, "3.12")
            self.assertEqual(defaults.worker_model, "")
            self.assertEqual(defaults.manager_model, "")

    def test_load_defaults_from_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cfg = root / "mminions.toml"
            cfg.write_text(
                """
[manager]
repo_path = "repo"
runs_root = "artifacts"
min_workers = 3
max_workers = 5
timeout_sec = 123
poll_interval_sec = 4
repro_validation_runs = 7
repro_min_matches = 5
validation_python_version = "3.13"
worker_model = "fast-model"
manager_model = "reasoning-model"
""".strip()
                + "\n",
                encoding="utf-8",
            )

            defaults = load_manager_defaults(cwd=root)

            self.assertEqual(defaults.repo_path, (root / "repo").resolve())
            self.assertEqual(defaults.runs_root, (root / "artifacts").resolve())
            self.assertEqual(defaults.min_workers, 3)
            self.assertEqual(defaults.max_workers, 5)
            self.assertEqual(defaults.timeout_sec, 123)
            self.assertEqual(defaults.poll_interval_sec, 4)
            self.assertEqual(defaults.repro_validation_runs, 7)
            self.assertEqual(defaults.repro_min_matches, 5)
            self.assertEqual(defaults.validation_python_version, "3.13")
            self.assertEqual(defaults.worker_model, "fast-model")
            self.assertEqual(defaults.manager_model, "reasoning-model")


if __name__ == "__main__":
    unittest.main()
