# repro-ddmin

Build deterministic bug reproducers, then minimize with semantic reduction + ddmin.

## Inputs
- issue spec JSON
- worker id
- repro candidate script and oracle command

## Workflow
1. Produce a candidate with setup, script, and oracle.
2. Validate determinism with 5 runs, require >=4 matching failure signatures.
3. Run semantic reduction pass (LLM).
4. Run ddmin on lines to remove non-essential code.
5. Re-validate after each accepted reduction.

## Output Schema
```json
{
  "candidate_id": "w1-candidate",
  "script": "...",
  "setup_commands": ["..."],
  "oracle_command": "...",
  "claimed_failure_signature": "...",
  "file_extension": "py"
}
```
