from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class Config:
    repo_path: Path
    runs_root: Path
    workers: int = 2
    timeout_sec: int = 300
    model: str = ""


def load_config(config_path: Path | None = None) -> Config:
    root = Path.cwd()
    path = config_path or root / "mminions.toml"

    cfg: dict = {}
    if path.exists():
        cfg = tomllib.loads(path.read_text()).get("manager", {})

    def resolve(key: str, default: Path) -> Path:
        if val := cfg.get(key):
            p = Path(val)
            return p if p.is_absolute() else (root / p).resolve()
        return default.resolve()

    return Config(
        repo_path=resolve("repo_path", root),
        runs_root=resolve("runs_root", root / "runs"),
        workers=max(1, min(6, int(cfg.get("workers", 2)))),
        timeout_sec=max(60, int(cfg.get("timeout_sec", 300))),
        model=str(cfg.get("model", "")),
    )
