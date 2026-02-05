---
name: execplan
description: Execute Codex ExecPlan documents milestone-by-milestone with strict validation and progress logging. Use when an ExecPlan already exists and implementation should follow explicit steps, checks, and decision tracking.
---

# ExecPlan

## Overview

Execute the existing plan exactly, then update it as a living record.
Treat each milestone as a contract: run, validate, log, continue.

## Workflow

1. Run preflight.
   - Read the full plan before executing commands.
   - Confirm milestones, dependencies, and validation exist.
   - Patch the plan first if critical ambiguity blocks execution.
2. Execute one milestone at a time.
   - Run steps in listed order.
   - Keep edits scoped to the active milestone.
   - Avoid opportunistic refactors.
3. Validate immediately.
   - Run milestone validation before starting the next one.
   - Keep debugging inside milestone scope when checks fail.
   - Mark a milestone complete only after checks pass.
4. Update plan while executing.
   - Check off completed items in `Progress`.
   - Append concrete notes to `Surprises & Discoveries`.
   - Append rationale to `Decision Log` when deviating.
5. Run final verification.
   - Run the plan's final validation section.
   - Summarize changed files, outputs, and residual risks.
6. Track runtime expectation.
   - Treat ExecPlan execution time as task-dependent.
   - Emit concise progress updates during long operations.

## Failure Modes To Prevent

- Skipping validation between milestones.
- Editing outside milestone scope without decision-log entries.
- Continuing after failed checks.
- Leaving plan progress stale.

## Input Contract

Require an ExecPlan with explicit milestone steps and validations.
Use `references/execution-checklist.md` before running the first command.

## Command Pattern

Use this headless pattern to execute an existing plan:

```bash
codex exec "$(cat plan.md)" -s workspace-write --skip-git-repo-check -o run-result.md
```
