# execplan-bugfix

Generate decision-complete execution plans for bug triage and minimal patch fixing.

## Inputs
- issue URL
- repo path
- known failure signal

## Output
- markdown ExecPlan with milestones
- concrete commands and validation gates
- risks and rollback checks

## Rules
- no code edits in planning step
- each milestone must include a deterministic pass/fail check
- include explicit artifacts under `runs/<run_id>/`
