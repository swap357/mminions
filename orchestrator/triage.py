from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json

from .types import TriageEvidence, TriageHypothesis


def _extract_json_payload(raw: str) -> dict:
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise json.JSONDecodeError("unable to locate JSON object", text, 0)
    return json.loads(text[start : end + 1])


def parse_triage_output(worker_id: str, output_path: Path) -> list[TriageHypothesis]:
    if not output_path.exists():
        return []
    raw = output_path.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    payload = _extract_json_payload(raw)
    hypotheses_payload = payload.get("hypotheses", [])

    hypotheses: list[TriageHypothesis] = []
    for idx, item in enumerate(hypotheses_payload, start=1):
        evidence = [
            TriageEvidence(
                file=str(ev.get("file", "")),
                line=int(ev.get("line", 0)),
                snippet=str(ev.get("snippet", "")),
            )
            for ev in item.get("evidence", [])
            if isinstance(ev, dict)
        ]
        hypothesis = TriageHypothesis(
            hypothesis_id=str(item.get("hypothesis_id") or f"{worker_id}-h{idx}"),
            mechanism=str(item.get("mechanism", "")).strip(),
            evidence=evidence,
            confidence=max(0.0, min(1.0, float(item.get("confidence", 0.0)))),
            disconfirming_checks=[str(x) for x in item.get("disconfirming_checks", [])],
            worker_id=worker_id,
        )
        hypotheses.append(hypothesis)
    return hypotheses


def _evidence_valid(repo_path: Path, evidence: TriageEvidence) -> bool:
    if not evidence.file or evidence.line <= 0:
        return False
    path = repo_path / evidence.file
    if not path.exists() or not path.is_file():
        return False
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if evidence.line > len(lines):
        return False
    line_text = lines[evidence.line - 1]
    if evidence.snippet and evidence.snippet not in line_text:
        return False
    return True


def _agreement_weight(mechanism: str, all_hypotheses: list[TriageHypothesis]) -> float:
    normalized = mechanism.strip().lower()
    if not normalized:
        return 0.0
    matches = sum(1 for hypothesis in all_hypotheses if hypothesis.mechanism.strip().lower() == normalized)
    max_matches = max(1, len({h.worker_id for h in all_hypotheses}))
    return min(1.0, matches / max_matches)


def _replay_consistency(mechanism: str, repro_text: str) -> float:
    if not mechanism.strip() or not repro_text.strip():
        return 0.0
    words = {word.lower() for word in mechanism.split() if len(word) >= 4}
    if not words:
        return 0.0
    repro_lower = repro_text.lower()
    overlaps = sum(1 for word in words if word in repro_lower)
    return min(1.0, overlaps / max(1, len(words)))


def rank_hypotheses(repo_path: Path, hypotheses: list[TriageHypothesis], repro_text: str) -> list[TriageHypothesis]:
    filtered: list[TriageHypothesis] = []
    for hypothesis in hypotheses:
        if not hypothesis.mechanism:
            continue
        if not hypothesis.evidence:
            continue
        valid_evidence = [ev for ev in hypothesis.evidence if _evidence_valid(repo_path, ev)]
        if not valid_evidence:
            continue
        filtered.append(replace(hypothesis, evidence=valid_evidence))

    ranked: list[TriageHypothesis] = []
    for hypothesis in filtered:
        evidence_score = min(1.0, len(hypothesis.evidence) / 3.0)
        agreement_score = _agreement_weight(hypothesis.mechanism, filtered)
        replay_score = _replay_consistency(hypothesis.mechanism, repro_text)
        confidence_score = hypothesis.confidence
        score = round(
            (0.4 * evidence_score)
            + (0.25 * agreement_score)
            + (0.2 * replay_score)
            + (0.15 * confidence_score),
            5,
        )
        ranked.append(replace(hypothesis, score=score))

    ranked.sort(key=lambda h: (-(h.score or 0.0), -h.confidence, h.hypothesis_id))
    return ranked


def top_hypotheses(ranked: list[TriageHypothesis], limit: int = 3) -> list[TriageHypothesis]:
    return ranked[:limit]
