# Responsibilities

## Hierarchy
1. `orchestrator` (launcher/control surface)
2. `manager` (run orchestrator)
3. `worker` (role executor)

## orchestrator
- Creates `run_id` and artifact skeleton.
- Starts/stops manager in tmux.
- Exposes `status`/`attach`/`send`/`stop` via CLI/server.

## manager
- Runs preflight and parses issue.
- Launches workers with prompts and isolated git worktrees.
- Monitors worker health/timeouts/restarts.
- Validates/chooses repros, runs minimization, ranks triage hypotheses.
- Writes `decision.json`, `final.md`, `run_done.json`.

## worker
- Executes one role (`REPRO_BUILDER` or `TRIAGER`).
- Reads prompt, runs `codex exec`, writes structured output file.
- Does not orchestrate other workers or finalize decisions.
