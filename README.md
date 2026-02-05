# mminions

Minimal orchestrator for bug repro + triage with Codex workers in tmux.

## Requirements
- Python 3.11+
- `codex`
- `tmux`
- `git`

## Run
```bash
python3 -m orchestrator.run \
  --issue-url https://github.com/<owner>/<repo>/issues/<number> \
  --repo-path /absolute/path/to/repo \
  --runs-root /absolute/path/to/runs \
  --min-workers 2 \
  --max-workers 6 \
  --timeout-sec 300
```

## Manager (direct)
```bash
python3 -m orchestrator.manager \
  --run-id run-20260205120000 \
  --issue-url https://github.com/<owner>/<repo>/issues/<number> \
  --repo-path /absolute/path/to/repo \
  --runs-root /absolute/path/to/runs
```

## CLI
```bash
python3 -m orchestrator.cli status --run-id <run_id> --runs-root /absolute/path/to/runs
python3 -m orchestrator.cli attach --run-id <run_id> --worker manager --runs-root /absolute/path/to/runs
python3 -m orchestrator.cli send --run-id <run_id> --worker w1 --text "status" --runs-root /absolute/path/to/runs
python3 -m orchestrator.cli stop --run-id <run_id> --runs-root /absolute/path/to/runs
```

## Artifacts
`runs/<run_id>/`
- `issue.json`
- `sessions.json`
- `repro/candidates/*.json`
- `repro/minimal_repro.*`
- `triage/hypotheses.json`
- `decision.json`
- `final.md`
- `run_done.json`

## Tests
```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```
