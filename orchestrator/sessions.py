from __future__ import annotations

from pathlib import Path
import json

from .artifacts import ArtifactStore


def read_sessions(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def require_sessions(run_id: str, runs_root: Path) -> dict:
    store = ArtifactStore(runs_root, run_id)
    path = store.paths.sessions_json
    sessions = read_sessions(path)
    if sessions is None:
        raise FileNotFoundError(f"run not found or missing sessions file: {path}")
    return sessions


def resolve_session_name(sessions: dict, worker: str) -> str:
    if worker == "manager":
        return sessions.get("manager", {}).get("session_name", "")
    worker_meta = sessions.get("workers", {}).get(worker, {})
    return worker_meta.get("session_name", "")


def iter_session_names(sessions: dict) -> list[str]:
    names: list[str] = []
    manager_name = sessions.get("manager", {}).get("session_name")
    if manager_name:
        names.append(manager_name)
    for worker in sessions.get("workers", {}).values():
        name = worker.get("session_name")
        if name:
            names.append(name)
    return names
