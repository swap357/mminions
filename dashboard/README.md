# mminions dashboard

Zero-dependency React frontend served by the status API server.

## Run

```bash
python3 -m orchestrator.server --runs-root /path/to/runs --port 8088
```

Open `http://127.0.0.1:8088` in a browser. The dashboard auto-discovers `dashboard/` relative to the project root.

Override with `--dashboard-dir /path/to/dashboard` if needed.

## Features

- **Status view** — run list, manager/worker pane output, summary bar, send commands, stop/launch runs
- **Timeline** — Gantt-style agent activity timeline, built from polling snapshots
- **Flow graph** — SVG node-edge graph showing manager→worker handoffs, colored by status

## Stack

- React 18 via CDN (no build step)
- Tailwind CSS via CDN
- Canvas timeline, SVG flow graph
- Polls API every 2.5s
