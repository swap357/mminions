from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class ArtifactPaths:
    run_dir: Path
    issue_json: Path
    sessions_json: Path
    repro_dir: Path
    repro_candidates_dir: Path
    minimal_repro_base: Path
    triage_dir: Path
    triage_hypotheses_json: Path
    decision_json: Path
    final_md: Path
    run_done_json: Path
    prompts_dir: Path
    scripts_dir: Path


class ArtifactStore:
    def __init__(self, runs_root: Path, run_id: str) -> None:
        self.runs_root = runs_root
        self.run_id = run_id
        run_dir = runs_root / run_id
        repro_dir = run_dir / "repro"
        triage_dir = run_dir / "triage"
        self.paths = ArtifactPaths(
            run_dir=run_dir,
            issue_json=run_dir / "issue.json",
            sessions_json=run_dir / "sessions.json",
            repro_dir=repro_dir,
            repro_candidates_dir=repro_dir / "candidates",
            minimal_repro_base=repro_dir / "minimal_repro",
            triage_dir=triage_dir,
            triage_hypotheses_json=triage_dir / "hypotheses.json",
            decision_json=run_dir / "decision.json",
            final_md=run_dir / "final.md",
            run_done_json=run_dir / "run_done.json",
            prompts_dir=run_dir / "prompts",
            scripts_dir=run_dir / "scripts",
        )

    def initialize_contract(self) -> ArtifactPaths:
        p = self.paths
        p.repro_candidates_dir.mkdir(parents=True, exist_ok=True)
        p.triage_dir.mkdir(parents=True, exist_ok=True)
        p.prompts_dir.mkdir(parents=True, exist_ok=True)
        p.scripts_dir.mkdir(parents=True, exist_ok=True)
        placeholder_repro = self.minimal_repro_path("txt")

        self.write_json(p.issue_json, {})
        self.write_json(p.sessions_json, {"manager": {}, "workers": {}})
        self.write_json(p.triage_hypotheses_json, {"hypotheses": []})
        self.write_json(p.decision_json, {})
        if not placeholder_repro.exists():
            placeholder_repro.write_text("", encoding="utf-8")
        if not p.final_md.exists():
            p.final_md.write_text("# mminions run\n\n", encoding="utf-8")
        return p

    def minimal_repro_path(self, file_extension: str = "py") -> Path:
        return self.paths.minimal_repro_base.with_suffix(f".{file_extension}")

    @staticmethod
    def write_json(path: Path, payload: object) -> None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def read_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))
