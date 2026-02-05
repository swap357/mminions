# triage-evidence

Produce root-cause hypotheses with repository evidence.

## Inputs
- minimal reproducer text
- issue spec JSON
- code search hints

## Rules
- no fix proposals
- each hypothesis needs evidence (`file`, `line`, `snippet`)
- include disconfirming checks
- confidence must be in [0, 1]

## Output Schema
```json
{
  "hypotheses": [
    {
      "hypothesis_id": "w1-h1",
      "mechanism": "...",
      "evidence": [{"file": "path", "line": 10, "snippet": "..."}],
      "confidence": 0.72,
      "disconfirming_checks": ["..."]
    }
  ]
}
```
