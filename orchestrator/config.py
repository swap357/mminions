from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os

try:
    import tomllib
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]
try:
    import tomli
except Exception:  # pragma: no cover
    tomli = None  # type: ignore[assignment]


DEFAULT_CONFIG_FILENAME = "mminions.toml"
ENV_CONFIG_PATH = "MMINIONS_CONFIG"


@dataclass(frozen=True)
class ManagerDefaults:
    repo_path: Path
    runs_root: Path
    min_workers: int = 1
    max_workers: int = 2
    timeout_sec: int = 300
    poll_interval_sec: int = 5
    repro_validation_runs: int = 5
    repro_min_matches: int = 1
    validation_python_version: str = "3.12"
    worker_model: str = ""
    manager_model: str = ""


def _as_int(payload: dict[str, Any], key: str, default: int) -> int:
    value = payload.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _default_repo_path(root: Path) -> Path:
    numpy_path = root / "projects" / "numpy"
    if numpy_path.exists():
        return numpy_path.resolve()
    return root.resolve()


def _resolve_path(raw_value: Any, root: Path, default_path: Path) -> Path:
    if not raw_value:
        return default_path.resolve()
    path = Path(str(raw_value).strip())
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def load_manager_defaults(config_path: str | None = None, cwd: Path | None = None) -> ManagerDefaults:
    root = (cwd or Path.cwd()).resolve()

    selected_config_path: Path | None = None
    if config_path:
        selected_config_path = Path(config_path).expanduser()
    elif os.getenv(ENV_CONFIG_PATH):
        selected_config_path = Path(os.environ[ENV_CONFIG_PATH]).expanduser()
    else:
        candidate = root / DEFAULT_CONFIG_FILENAME
        if candidate.exists():
            selected_config_path = candidate

    manager_payload: dict[str, Any] = {}
    if selected_config_path is not None:
        if not selected_config_path.exists():
            raise FileNotFoundError(f"config file not found: {selected_config_path}")
        payload = _parse_toml(selected_config_path.read_text(encoding="utf-8"))
        manager_payload = payload.get("manager", {}) if isinstance(payload, dict) else {}
        if not isinstance(manager_payload, dict):
            manager_payload = {}

    repo_path = _resolve_path(manager_payload.get("repo_path"), root, _default_repo_path(root))
    runs_root = _resolve_path(manager_payload.get("runs_root"), root, root / "runs")
    min_workers = max(2, _as_int(manager_payload, "min_workers", 2))
    max_workers = min(6, max(2, _as_int(manager_payload, "max_workers", 6)))
    timeout_sec = max(60, _as_int(manager_payload, "timeout_sec", 300))
    poll_interval_sec = max(1, _as_int(manager_payload, "poll_interval_sec", 5))
    repro_validation_runs = max(1, _as_int(manager_payload, "repro_validation_runs", 5))
    repro_min_matches = max(1, min(_as_int(manager_payload, "repro_min_matches", 1), repro_validation_runs))
    validation_python_version = str(manager_payload.get("validation_python_version", "3.12")).strip() or "3.12"
    worker_model = str(manager_payload.get("worker_model", "")).strip()
    manager_model = str(manager_payload.get("manager_model", "")).strip()

    return ManagerDefaults(
        repo_path=repo_path,
        runs_root=runs_root,
        min_workers=min_workers,
        max_workers=max_workers,
        timeout_sec=timeout_sec,
        poll_interval_sec=poll_interval_sec,
        repro_validation_runs=repro_validation_runs,
        repro_min_matches=repro_min_matches,
        validation_python_version=validation_python_version,
        worker_model=worker_model,
        manager_model=manager_model,
    )


def _parse_toml(raw: str) -> dict[str, Any]:
    if tomllib is not None:
        return tomllib.loads(raw)
    if tomli is not None:
        return tomli.loads(raw)
    return _parse_minimal_toml(raw)


def _parse_minimal_toml(raw: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    current = payload
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].strip()
            if not section:
                continue
            section_payload = payload.get(section)
            if not isinstance(section_payload, dict):
                section_payload = {}
                payload[section] = section_payload
            current = section_payload
            continue
        if "=" not in stripped:
            continue
        key, value_raw = stripped.split("=", 1)
        key = key.strip()
        value = value_raw.strip()
        if not key:
            continue
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            current[key] = value[1:-1]
            continue
        if value.startswith("'") and value.endswith("'") and len(value) >= 2:
            current[key] = value[1:-1]
            continue
        try:
            current[key] = int(value)
        except ValueError:
            current[key] = value
    return payload
