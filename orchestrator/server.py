from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
import argparse
import json
import threading
from urllib.parse import parse_qs, urlparse
import mimetypes

from .artifacts import ArtifactStore
from .command import CommandRunner
from .run import LauncherConfig, launch_manager
from .sessions import iter_session_names, read_sessions, resolve_session_name
from .tmux_supervisor import TmuxSupervisor


@dataclass(frozen=True)
class ServerConfig:
    runs_root: Path
    host: str
    port: int
    capture_lines: int
    dashboard_dir: Path | None = None


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_runs(runs_root: Path) -> list[str]:
    if not runs_root.exists():
        return []
    runs = [p.name for p in runs_root.iterdir() if p.is_dir()]
    return sorted(runs)


def _status_summary(workers: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {
        "total": len(workers),
        "active": 0,
        "finished": 0,
        "failed": 0,
        "timeout": 0,
        "unknown": 0,
    }
    for worker in workers:
        if worker.get("session_exists"):
            summary["active"] += 1
        status = worker.get("status", "unknown")
        if status in summary:
            summary[status] += 1
        elif status:
            summary["unknown"] += 1
    return summary


def build_run_status(
    run_id: str,
    runs_root: Path,
    tmux: TmuxSupervisor,
    capture_lines: int,
) -> dict[str, Any]:
    store = ArtifactStore(runs_root, run_id)
    paths = store.paths
    if not paths.run_dir.exists():
        raise FileNotFoundError(f"run not found: {paths.run_dir}")

    sessions = read_sessions(paths.sessions_json) or {"manager": {}, "workers": {}}
    decision = _read_json(paths.decision_json)
    run_done = _read_json(paths.run_done_json)

    manager_meta = sessions.get("manager", {}) if isinstance(sessions, dict) else {}
    manager_name = manager_meta.get("session_name", "")
    manager_exists = tmux.session_exists(manager_name) if manager_name else False
    manager_tail = tmux.capture_pane(manager_name, lines=capture_lines) if manager_exists else ""

    workers_meta = sessions.get("workers", {}) if isinstance(sessions, dict) else {}
    workers: list[dict[str, Any]] = []
    for worker_id in sorted(workers_meta.keys()):
        metadata = workers_meta.get(worker_id, {})
        session_name = metadata.get("session_name", "")
        session_exists = tmux.session_exists(session_name) if session_name else False
        tail = tmux.capture_pane(session_name, lines=capture_lines) if session_exists else ""
        workers.append(
            {
                "worker_id": worker_id,
                "role": metadata.get("role", ""),
                "status": metadata.get("status", "unknown"),
                "session_name": session_name,
                "session_exists": session_exists,
                "worktree_path": metadata.get("worktree_path", ""),
                "output_path": metadata.get("output_path", ""),
                "script_path": metadata.get("script_path", ""),
                "pane_tail": tail,
            }
        )

    if run_done:
        run_state = "done"
    elif manager_exists or any(worker.get("session_exists") for worker in workers):
        run_state = "running"
    elif paths.sessions_json.exists():
        run_state = "stopped"
    else:
        run_state = "unknown"

    return {
        "run_id": run_id,
        "run_state": run_state,
        "manager": {
            "session_name": manager_name,
            "session_exists": manager_exists,
            "pane_tail": manager_tail,
            "issue_url": manager_meta.get("issue_url", ""),
        },
        "workers": workers,
        "summary": _status_summary(workers),
        "decision": decision or {},
        "run_done": run_done or {},
    }


def launch_run(
    payload: dict[str, Any],
    runs_root: Path,
    launcher=launch_manager,
) -> dict[str, Any]:
    issue_url = payload.get("issue_url", "")
    repo_path = payload.get("repo_path", "")
    if not issue_url or not repo_path:
        raise ValueError("issue_url and repo_path are required")

    min_workers = int(payload.get("min_workers", 2))
    max_workers = int(payload.get("max_workers", 6))
    timeout_sec = int(payload.get("timeout_sec", 300))

    config = LauncherConfig(
        issue_url=issue_url,
        repo_path=Path(repo_path).resolve(),
        runs_root=runs_root.resolve(),
        min_workers=max(2, min_workers),
        max_workers=min(6, max(2, max_workers)),
        timeout_sec=max(60, timeout_sec),
        detach=True,
    )
    run_id, run_done_json = launcher(config)
    return {
        "run_id": run_id,
        "run_done": str(run_done_json),
        "manager_session": f"codorch-{run_id}-manager",
    }


def stop_run(run_id: str, runs_root: Path, tmux: TmuxSupervisor) -> dict[str, Any]:
    store = ArtifactStore(runs_root, run_id)
    sessions = read_sessions(store.paths.sessions_json) or {"manager": {}, "workers": {}}
    for name in iter_session_names(sessions):
        tmux.kill_session(name)

    if not store.paths.run_done_json.exists():
        store.write_json(
            store.paths.run_done_json,
            {
                "run_id": run_id,
                "status": "stopped",
                "final_md": str(store.paths.final_md),
                "decision_json": str(store.paths.decision_json),
            },
        )
    return {"run_id": run_id, "status": "stopped"}


def send_to_worker(run_id: str, runs_root: Path, tmux: TmuxSupervisor, worker: str, text: str) -> dict[str, Any]:
    store = ArtifactStore(runs_root, run_id)
    sessions = read_sessions(store.paths.sessions_json) or {"manager": {}, "workers": {}}
    session_name = resolve_session_name(sessions, worker)
    if not session_name:
        raise ValueError(f"unknown worker: {worker}")
    tmux.send_text(session_name, text, press_enter=True)
    return {"run_id": run_id, "worker": worker, "sent": True}


class StatusHandler(BaseHTTPRequestHandler):
    server_version = "mminions-status/0.1"

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/runs":
            runs = list_runs(self.server.config.runs_root)
            payload = {
                "runs": runs,
                "count": len(runs),
            }
            self._send_json(payload)
            return

        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/status"):
            run_id = parsed.path.split("/")[3]
            try:
                capture_lines = self._capture_lines(parsed)
                payload = build_run_status(
                    run_id=run_id,
                    runs_root=self.server.config.runs_root,
                    tmux=self.server.tmux,
                    capture_lines=capture_lines,
                )
            except FileNotFoundError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(payload)
            return

        self._serve_dashboard(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/runs":
            payload = self._read_json_body()
            if payload is None:
                return
            try:
                response = launch_run(payload, self.server.config.runs_root)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(response, status=HTTPStatus.CREATED)
            return

        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/stop"):
            run_id = parsed.path.split("/")[3]
            response = stop_run(run_id, self.server.config.runs_root, self.server.tmux)
            self._send_json(response)
            return

        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/send"):
            run_id = parsed.path.split("/")[3]
            payload = self._read_json_body()
            if payload is None:
                return
            worker = payload.get("worker", "")
            text = payload.get("text", "")
            if not worker or not text:
                self._send_json({"error": "worker and text are required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                response = send_to_worker(run_id, self.server.config.runs_root, self.server.tmux, worker, text)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(response)
            return

        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        if getattr(self.server, "quiet", False):
            return
        super().log_message(format, *args)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_dashboard(self, path: str) -> None:
        dashboard_dir = getattr(self.server, "dashboard_dir", None)
        if dashboard_dir is None:
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        rel = path.lstrip("/") or "index.html"
        if rel == "":
            rel = "index.html"
        file_path = (dashboard_dir / rel).resolve()
        if not str(file_path).startswith(str(dashboard_dir.resolve())):
            self._send_json({"error": "forbidden"}, status=HTTPStatus.FORBIDDEN)
            return
        if not file_path.is_file():
            file_path = dashboard_dir / "index.html"
        if not file_path.is_file():
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        content_type, _ = mimetypes.guess_type(str(file_path))
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _capture_lines(self, parsed) -> int:
        default_lines = self.server.config.capture_lines
        params = parse_qs(parsed.query)
        if "lines" not in params:
            return default_lines
        try:
            value = int(params["lines"][0])
        except (ValueError, TypeError):
            return default_lines
        return max(10, min(500, value))

    def _read_json_body(self) -> dict[str, Any] | None:
        length = self.headers.get("Content-Length")
        if length is None:
            self._send_json({"error": "missing request body"}, status=HTTPStatus.BAD_REQUEST)
            return None
        try:
            raw = self.rfile.read(int(length))
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "invalid json body"}, status=HTTPStatus.BAD_REQUEST)
            return None
        if not isinstance(payload, dict):
            self._send_json({"error": "json body must be an object"}, status=HTTPStatus.BAD_REQUEST)
            return None
        return payload


class StatusServer(HTTPServer):
    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self.runner = CommandRunner()
        self.tmux = TmuxSupervisor(self.runner, cwd=Path.cwd())
        self.quiet = False
        self.dashboard_dir = config.dashboard_dir
        super().__init__((config.host, config.port), StatusHandler)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="mminions status API server")
    parser.add_argument("--runs-root", default="runs")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--capture-lines", type=int, default=120)
    parser.add_argument("--quiet", action="store_true", default=False)
    parser.add_argument("--dashboard-dir", default=None, help="path to dashboard static files")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    dashboard_dir = None
    if args.dashboard_dir:
        dashboard_dir = Path(args.dashboard_dir).resolve()
    else:
        default_dashboard = Path(__file__).resolve().parent.parent / "dashboard"
        if default_dashboard.is_dir():
            dashboard_dir = default_dashboard
    config = ServerConfig(
        runs_root=Path(args.runs_root).resolve(),
        host=args.host,
        port=args.port,
        capture_lines=max(10, min(500, args.capture_lines)),
        dashboard_dir=dashboard_dir,
    )
    server = StatusServer(config)
    server.quiet = args.quiet

    started = datetime.now(timezone.utc).isoformat()
    print(f"status server listening on http://{config.host}:{config.port} (started {started})")
    print(f"runs_root={config.runs_root}")
    if config.dashboard_dir:
        print(f"dashboard={config.dashboard_dir}")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
