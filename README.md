# mminions

Tmux session deployment for CLI agents.

## Install

```bash
uv pip install -e .
```

## Usage

```bash
# Run bug repro + triage on a GitHub issue
mminions-run --issue-url https://github.com/owner/repo/issues/123

# List active sessions
mminions ls

# Attach to a session
mminions attach mm-run-xyz-repro-w1

# Kill all sessions
mminions kill --all
```

## Config

Edit `mminions.toml`:

```toml
[manager]
repo_path = "path/to/repo"
runs_root = "runs"
workers = 2
timeout_sec = 300
model = ""
```
