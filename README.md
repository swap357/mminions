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

## Status API server
```bash
python3 -m orchestrator.server --runs-root /absolute/path/to/runs --host 127.0.0.1 --port 8088
```

Endpoints:
- `GET /health`
- `GET /api/runs`
- `GET /api/runs/<run_id>/status?lines=120`
- `POST /api/runs`
- `POST /api/runs/<run_id>/stop`
- `POST /api/runs/<run_id>/send`

### API formats

`GET /health`
Response:
```json
{
  "ok": true
}
```

`GET /api/runs`
Response:
```json
{
  "runs": ["run-20260205123000", "run-20260205124500"],
  "count": 2
}
```

`GET /api/runs/<run_id>/status?lines=120`
Response:
```json
{
  "run_id": "run-20260205123000",
  "run_state": "running",
  "manager": {
    "session_name": "codorch-run-20260205123000-manager",
    "session_exists": true,
    "pane_tail": "last output lines...",
    "issue_url": "https://github.com/<owner>/<repo>/issues/<number>"
  },
  "workers": [
    {
      "worker_id": "w1",
      "role": "REPRO_BUILDER",
      "status": "finished",
      "session_name": "codorch-run-20260205123000-w1",
      "session_exists": false,
      "worktree_path": "/tmp/mminions-run-20260205123000-w1",
      "output_path": "/absolute/path/to/runs/run-20260205123000/repro/candidates/w1.json",
      "script_path": "/absolute/path/to/runs/run-20260205123000/scripts/repro-w1.sh",
      "pane_tail": ""
    }
  ],
  "summary": {
    "total": 1,
    "active": 0,
    "finished": 1,
    "failed": 0,
    "timeout": 0,
    "unknown": 0
  },
  "decision": {
    "status": "running"
  },
  "run_done": {}
}
```

`POST /api/runs`
Request:
```json
{
  "issue_url": "https://github.com/<owner>/<repo>/issues/<number>",
  "repo_path": "/absolute/path/to/repo",
  "min_workers": 2,
  "max_workers": 6,
  "timeout_sec": 300
}
```
Response:
```json
{
  "run_id": "run-20260205123000",
  "run_done": "/absolute/path/to/runs/run-20260205123000/run_done.json",
  "manager_session": "codorch-run-20260205123000-manager"
}
```

`POST /api/runs/<run_id>/stop`
Response:
```json
{
  "run_id": "run-20260205123000",
  "status": "stopped"
}
```

`POST /api/runs/<run_id>/send`
Request:
```json
{
  "worker": "w1",
  "text": "status"
}
```
Response:
```json
{
  "run_id": "run-20260205123000",
  "worker": "w1",
  "sent": true
}
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
