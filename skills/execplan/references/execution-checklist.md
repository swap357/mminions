# ExecPlan Execution Checklist

## Before Running

- Read the entire ExecPlan once.
- Confirm each milestone has:
  - Scope
  - Step list with commands
  - Validation commands and explicit pass conditions
- Confirm required tools and files exist.
- Identify risky operations and fallback options.

## During Execution

Repeat per milestone:

1. Run steps in the listed order.
2. Keep edits inside milestone scope.
3. Run milestone validation immediately.
4. Update `Progress` checkbox only on pass.
5. Append relevant notes to:
   - `Surprises & Discoveries`
   - `Decision Log`

## Stop Conditions

- Validation fails and cause is unknown.
- Plan instructions conflict with current repository state.
- A required dependency is missing.

When stopped:
- Log what failed.
- Patch the ExecPlan with a corrective step.
- Resume from the active milestone only after updating the plan.

## Finalization

- Run final integration validation.
- Summarize changed files and remaining risks.
- Confirm plan progress reflects actual completion.
