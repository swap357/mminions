import json
import tempfile
import unittest
from pathlib import Path

from orchestrator.artifacts import ArtifactStore
from orchestrator.server import build_run_status, launch_run, list_runs, send_to_worker, stop_run


class FakeTmux:
    def __init__(self, existing=None, panes=None):
        self.existing = set(existing or [])
        self.panes = dict(panes or {})
        self.killed = []
        self.sent = []

    def session_exists(self, name: str) -> bool:
        return name in self.existing

    def capture_pane(self, name: str, lines: int = 200) -> str:
        return self.panes.get(name, "")

    def kill_session(self, name: str) -> None:
        self.killed.append(name)

    def send_text(self, name: str, text: str, press_enter: bool = True) -> None:
        self.sent.append((name, text, press_enter))


class ServerTests(unittest.TestCase):
    def test_list_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "run-1").mkdir()
            (root / "run-2").mkdir()
            (root / "notes").mkdir()
            self.assertEqual(list_runs(root), ["notes", "run-1", "run-2"])

    def test_build_run_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "run-20260205120000"
            store = ArtifactStore(root, run_id)
            paths = store.initialize_contract()

            sessions = {
                "manager": {"session_name": "codorch-run-manager", "issue_url": "https://example.com"},
                "workers": {
                    "w1": {"session_name": "codorch-w1", "role": "REPRO_BUILDER", "status": "finished"},
                    "w2": {"session_name": "codorch-w2", "role": "TRIAGER", "status": "failed"},
                },
            }
            paths.sessions_json.write_text(json.dumps(sessions), encoding="utf-8")
            paths.decision_json.write_text(json.dumps({"status": "running"}), encoding="utf-8")

            tmux = FakeTmux(existing={"codorch-run-manager", "codorch-w1"}, panes={"codorch-w1": "ok"})
            status = build_run_status(run_id, root, tmux=tmux, capture_lines=50)

            self.assertEqual(status["run_id"], run_id)
            self.assertEqual(status["run_state"], "running")
            self.assertTrue(status["manager"]["session_exists"])
            self.assertEqual(status["workers"][0]["worker_id"], "w1")
            self.assertEqual(status["workers"][0]["pane_tail"], "ok")
            self.assertEqual(status["summary"]["total"], 2)
            self.assertEqual(status["summary"]["active"], 1)
            self.assertEqual(status["summary"]["failed"], 1)

    def test_build_run_status_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "run-20260205120001"
            store = ArtifactStore(root, run_id)
            paths = store.initialize_contract()
            paths.run_done_json.write_text(json.dumps({"status": "ok"}), encoding="utf-8")

            tmux = FakeTmux()
            status = build_run_status(run_id, root, tmux=tmux, capture_lines=50)

            self.assertEqual(status["run_state"], "done")

    def test_launch_run_validates_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def fake_launcher(config):
                return "run-123", root / "run-123" / "run_done.json"

            payload = {"issue_url": "https://example.com", "repo_path": "/tmp/repo"}
            result = launch_run(payload, root, launcher=fake_launcher)

            self.assertEqual(result["run_id"], "run-123")
            self.assertIn("manager_session", result)

    def test_launch_run_uses_workers_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            captured = {}

            def fake_launcher(config):
                captured["workers"] = config.workers
                return "run-123", root / "run-123" / "run_done.json"

            payload = {
                "issue_url": "https://example.com",
                "repo_path": "/tmp/repo",
                "workers": 4,
            }
            launch_run(payload, root, launcher=fake_launcher)

            self.assertEqual(captured["workers"], 4)

    def test_stop_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "run-20260205160000"
            store = ArtifactStore(root, run_id)
            paths = store.initialize_contract()

            sessions = {
                "manager": {"session_name": "codorch-run-manager"},
                "workers": {
                    "w1": {"session_name": "codorch-w1"},
                    "w2": {"session_name": "codorch-w2"},
                },
            }
            paths.sessions_json.write_text(json.dumps(sessions), encoding="utf-8")

            tmux = FakeTmux()
            result = stop_run(run_id, root, tmux=tmux)

            self.assertEqual(result["status"], "stopped")
            self.assertEqual(sorted(tmux.killed), ["codorch-run-manager", "codorch-w1", "codorch-w2"])
            self.assertTrue(paths.run_done_json.exists())

    def test_send_to_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "run-20260205160001"
            store = ArtifactStore(root, run_id)
            paths = store.initialize_contract()

            sessions = {
                "manager": {"session_name": "codorch-run-manager"},
                "workers": {"w1": {"session_name": "codorch-w1"}},
            }
            paths.sessions_json.write_text(json.dumps(sessions), encoding="utf-8")

            tmux = FakeTmux()
            result = send_to_worker(run_id, root, tmux=tmux, worker="w1", text="status")

            self.assertTrue(result["sent"])
            self.assertEqual(tmux.sent[0][0], "codorch-w1")


if __name__ == "__main__":
    unittest.main()
