from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable
import json
import re
import shlex

from .command import CommandRunner
from .types import FailureSignal, IssueSpec, ReproCandidate, ValidationResult


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


def parse_repro_candidate(worker_id: str, output_path: Path) -> ReproCandidate | None:
    if not output_path.exists():
        return None
    raw = output_path.read_text(encoding="utf-8").strip()
    if not raw:
        return None

    data = _extract_json_payload(raw)
    return ReproCandidate(
        candidate_id=str(data.get("candidate_id") or f"{worker_id}-candidate"),
        worker_id=worker_id,
        script=str(data["script"]),
        setup_commands=[str(cmd) for cmd in data.get("setup_commands", [])],
        oracle_command=str(data["oracle_command"]),
        claimed_failure_signature=str(data["claimed_failure_signature"]),
        file_extension=str(data.get("file_extension") or "py"),
    )


def _signature_matches(output: str, claimed_signature: str, expected_signals: list[FailureSignal]) -> bool:
    lowered_output = output.lower()
    if claimed_signature.lower() in lowered_output:
        return True
    for signal in expected_signals:
        if signal.exception_type and signal.exception_type.lower() in lowered_output:
            return True
        if signal.message_substring and signal.message_substring.lower() in lowered_output:
            return True
    return False


def validate_candidate(
    candidate: ReproCandidate,
    issue_spec: IssueSpec,
    repo_path: Path,
    candidate_script_path: Path,
    command_runner: CommandRunner,
    runs: int = 5,
    min_matches: int = 3,
    python_executable: str | None = None,
    timeout_sec: int = 30,
) -> ValidationResult:
    candidate_script_path.write_text(candidate.script, encoding="utf-8")

    for setup_cmd in candidate.setup_commands:
        rendered_setup = setup_cmd.replace("{repro_file}", str(candidate_script_path))
        rendered_setup = _render_python_command(rendered_setup, python_executable)
        setup_result = command_runner.run_shell(rendered_setup, cwd=repo_path, timeout_sec=timeout_sec)
        if setup_result.returncode != 0:
            return ValidationResult(
                total_runs=runs,
                matches=0,
                matched_signature=candidate.claimed_failure_signature,
                passed=False,
            )

    matches = 0
    for _ in range(runs):
        oracle_cmd = candidate.oracle_command.replace("{repro_file}", str(candidate_script_path))
        oracle_cmd = _render_python_command(oracle_cmd, python_executable)
        run_result = command_runner.run_shell(oracle_cmd, cwd=repo_path, timeout_sec=timeout_sec)
        output = f"{run_result.stdout}\n{run_result.stderr}"
        if _signature_matches(output, candidate.claimed_failure_signature, issue_spec.expected_failure_signals):
            matches += 1

    required_matches = max(1, min(min_matches, runs))
    passed = matches >= required_matches
    return ValidationResult(
        total_runs=runs,
        matches=matches,
        matched_signature=candidate.claimed_failure_signature,
        passed=passed,
    )


def score_candidate(candidate: ReproCandidate, issue_spec: IssueSpec) -> float:
    if candidate.validation is None:
        return 0.0

    determinism = candidate.validation.matches / max(candidate.validation.total_runs, 1)

    expected_terms: list[str] = []
    for signal in issue_spec.expected_failure_signals:
        if signal.exception_type:
            expected_terms.append(signal.exception_type.lower())
        if signal.message_substring:
            expected_terms.append(signal.message_substring.lower())

    lower_claim = candidate.claimed_failure_signature.lower()
    fidelity = 1.0 if any(term in lower_claim for term in expected_terms) else 0.0

    line_count = max(1, len(candidate.script.splitlines()))
    size_score = max(0.0, 1.0 - (min(line_count, 200) / 200.0))

    return round((0.6 * determinism) + (0.25 * fidelity) + (0.15 * size_score), 5)


def choose_best_candidate(candidates: list[ReproCandidate], issue_spec: IssueSpec) -> ReproCandidate | None:
    scored: list[ReproCandidate] = []
    for candidate in candidates:
        scored.append(replace(candidate, score=score_candidate(candidate, issue_spec)))

    viable = [candidate for candidate in scored if candidate.validation and candidate.validation.passed]
    if not viable:
        return None

    return sorted(
        viable,
        key=lambda c: (
            -(c.score or 0.0),
            len(c.script.splitlines()),
            c.candidate_id,
        ),
    )[0]


def _extract_code_block(text: str) -> str:
    stripped = text.strip()
    if "```" not in stripped:
        return stripped

    chunks = stripped.split("```")
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        if "\n" in chunk:
            first, rest = chunk.split("\n", 1)
            if first.isalpha() or first in {"python", "py", "text"}:
                return rest.strip()
        return chunk
    return stripped


def semantic_reduce_script(
    script: str,
    issue_spec: IssueSpec,
    command_runner: CommandRunner,
    repo_path: Path,
    output_path: Path,
    model: str = "",
    telemetry_jsonl_path: Path | None = None,
) -> str:
    prompt = (
        "You are minimizing a bug reproducer. Return only code.\n"
        "Goal: preserve the same failure signature and root-cause shape while removing noise.\n"
        f"Issue: {issue_spec.title}\n"
        f"Expected signals: {[s.exception_type or s.message_substring for s in issue_spec.expected_failure_signals]}\n"
        "Code:\n"
        "```python\n"
        f"{script}\n"
        "```\n"
    )

    args = [
        "codex",
        "exec",
        prompt,
    ]
    if model.strip():
        args.extend(["-m", model.strip()])
    args.extend(
        [
            "-s",
            "read-only",
            "--skip-git-repo-check",
            "-C",
            str(repo_path),
            "-o",
            str(output_path),
            "--json",
        ]
    )
    result = command_runner.run(args, cwd=repo_path, timeout_sec=120)
    if telemetry_jsonl_path is not None:
        telemetry_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        telemetry_jsonl_path.write_text(result.stdout or "", encoding="utf-8")
    if result.returncode != 0 or not output_path.exists():
        return script

    return _extract_code_block(output_path.read_text(encoding="utf-8"))


def _ddmin(lines: list[str], oracle: Callable[[list[str]], bool]) -> list[str]:
    if not lines:
        return lines

    n = 2
    current = lines[:]

    while len(current) >= 2:
        chunk_size = len(current) // n
        if chunk_size == 0:
            break

        found_reduction = False
        for i in range(n):
            start = i * chunk_size
            end = len(current) if i == (n - 1) else (i + 1) * chunk_size
            trial = current[:start] + current[end:]
            if trial and oracle(trial):
                current = trial
                n = max(2, n - 1)
                found_reduction = True
                break

        if not found_reduction:
            if n >= len(current):
                break
            n = min(len(current), n * 2)

    return current


def minimize_candidate(
    candidate: ReproCandidate,
    issue_spec: IssueSpec,
    repo_path: Path,
    command_runner: CommandRunner,
    semantic_output_path: Path,
    minimal_output_path: Path,
    min_matches: int = 3,
    python_executable: str | None = None,
    model: str = "",
    telemetry_jsonl_path: Path | None = None,
    timeout_sec: int = 30,
) -> ReproCandidate:
    semantic_script = semantic_reduce_script(
        script=candidate.script,
        issue_spec=issue_spec,
        command_runner=command_runner,
        repo_path=repo_path,
        output_path=semantic_output_path,
        model=model,
        telemetry_jsonl_path=telemetry_jsonl_path,
    )

    base_script = semantic_script if semantic_script.strip() else candidate.script
    base_lines = base_script.splitlines()

    def oracle(lines: list[str]) -> bool:
        script = "\n".join(lines).strip() + "\n"
        probe = replace(candidate, script=script)
        validation = validate_candidate(
            candidate=probe,
            issue_spec=issue_spec,
            repo_path=repo_path,
            candidate_script_path=minimal_output_path,
            command_runner=command_runner,
            runs=5,
            min_matches=min_matches,
            python_executable=python_executable,
            timeout_sec=timeout_sec,
        )
        return validation.passed

    minimized_lines = _ddmin(base_lines, oracle)
    minimized_script = "\n".join(minimized_lines).strip() + "\n"

    validated = validate_candidate(
        candidate=replace(candidate, script=minimized_script),
        issue_spec=issue_spec,
        repo_path=repo_path,
        candidate_script_path=minimal_output_path,
        command_runner=command_runner,
        runs=5,
        min_matches=min_matches,
        python_executable=python_executable,
        timeout_sec=timeout_sec,
    )

    return replace(candidate, script=minimized_script, validation=validated)


def _render_python_command(command: str, python_executable: str | None) -> str:
    if not python_executable:
        return command
    python_token = shlex.quote(python_executable)
    rendered = command.replace("{python}", python_token)
    return re.sub(r"(?<![\\w/.-])python(?![\\w/.-])", python_token, rendered)
