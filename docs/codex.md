# Codex CLI Capabilities (Manager Reference)

## Non-interactive (headless)

```bash
# Plan mode (read-only)
codex exec "<prompt>" -s read-only --skip-git-repo-check -o <file>

# Edit mode
codex exec "<prompt>" -s workspace-write --skip-git-repo-check -o <file>

# Full auto
codex exec "<prompt>" --full-auto -o <file>
```

## Key Flags

- `exec` non-interactive mode
- `-s, --sandbox read-only|workspace-write|danger-full-access`
- `--full-auto` (workspace-write + approval on-failure)
- `-o, --output-last-message <file>` capture output
- `-m, --model <name>`
- `-C, --cd <dir>`
- `--add-dir <path>`
- `--skip-git-repo-check`
- `--json` structured event output
- `--dangerously-bypass-approvals-and-sandbox` (explicit approval only)

## Worktrees (Parallel Isolation)

Source: https://developers.openai.com/codex/app/worktrees

Git worktrees enable multiple workers to edit the same repo concurrently without conflicts.
Each worktree = separate checkout, shared `.git`, independent files.

### Manager Usage

```bash
# Create isolated worktrees for parallel workers
git worktree add /tmp/worker-claude -d  # detached HEAD
git worktree add /tmp/worker-codex -d

# Run workers in separate worktrees
codex exec "<plan>" -s workspace-write -C /tmp/worker-codex -o result.txt
claude -p "<plan>" --permission-mode acceptEdits --cwd /tmp/worker-claude

# Merge results
cd /path/to/repo
git diff /tmp/worker-claude HEAD > claude.patch
git diff /tmp/worker-codex HEAD > codex.patch

# Cleanup
git worktree remove /tmp/worker-claude
git worktree remove /tmp/worker-codex
```

### Why Worktrees

- **No file conflicts**: workers edit independently
- **Atomic results**: diff each worktree against HEAD
- **Conflict detection**: compare patches before applying
- **Cheap**: shared `.git`, only working files duplicated

### Rules

- One branch per worktree (git enforces this)
- Detached HEAD avoids branch collision
- Worktrees share history, so `git diff` against base works

## Failure Modes

- Stale login requires `codex login`.
- Headless runs can hang if approvals are required.

## Escalation Pattern

1. `read-only` + `--ask-for-approval never`
2. `workspace-write`
3. `danger-full-access` only with explicit approval

## Tools

| Tool | Purpose |
|------|---------|
| `shell` | commands |
| `read_file` | read files |
| `write_file` | create/overwrite |
| `edit_file` | patch-based edits |
| `list_dir` | directory listing |

Access governed by sandbox:
- `read-only`: read_file, list_dir
- `workspace-write`: + write_file, edit_file
- `danger-full-access`: unrestricted

## Skills

No built-in `/skill` system.

Manager workaround: prompt templates.
```
codex exec "Analyze staged changes. Write commit message. Commit." ...
```

## Subagents

No internal subagent spawning.

- Claude: agent spawns `Task(subagent_type=...)` internally
- Codex: single-threaded, manager must orchestrate

## ExecPlans

Codex works best with **self-contained plan documents**, not simple prompts.

Source: https://cookbook.openai.com/articles/codex_exec_plans

### What Is an ExecPlan

A structured markdown document that gives Codex everything needed to execute autonomously:
- Purpose (user-visible value)
- Context (repo layout, key files, conventions)
- Milestones (ordered, independently verifiable)
- Concrete steps (exact commands, working dirs, expected output)
- Validation (how to verify each milestone)

### Why ExecPlans

- Self-contained: no external context needed
- Milestone-driven: each step verifiable before moving on
- Idempotent: steps can be retried safely
- Living document: progress, surprises, decisions tracked inline

### Manager Pattern: Generate Then Execute

```python
# 1. Generate plan (read-only)
plan = await run_codex(
    "Create an ExecPlan for: {task.goal}. Include milestones, concrete steps, validation.",
    sandbox="read-only"
)

# 2. Execute plan (workspace-write)
await run_codex(plan, sandbox="workspace-write")
```

### ExecPlan Skeleton

```markdown
# ExecPlan: <title>

## Purpose
<what user-visible value this delivers>

## Context
<repo structure, key files, conventions>

## Progress
- [ ] Milestone 1
- [ ] Milestone 2

## Milestones

### Milestone 1: <name>
**Scope:** <what changes>
**Steps:**
1. <exact command, working dir>
   Expected: <output snippet>
2. ...
**Validation:** <how to verify>

### Milestone 2: <name>
...

## Surprises & Discoveries
<updated as work progresses>

## Decision Log
<design choices with rationale>
```

## Delegation Patterns

Manager-level orchestration required. Codex is single-threaded.

**Plan → Execute (ExecPlan-driven)**
```
codex exec "generate ExecPlan for X" -s read-only -o plan.md
codex exec "$(cat plan.md)" -s workspace-write -o result.txt
```

**Parallel (manager-driven)**
```python
results = await asyncio.gather(
    run_codex("task A", sandbox="read-only"),
    run_codex("task B", sandbox="read-only"),
)
combined = aggregate(results)
await run_codex(f"execute based on: {combined}", sandbox="workspace-write")
```

**Escalating sandbox**
```
read-only → generate plan + identify files
workspace-write → execute milestones
```

Each invocation stateless. Pass full context in prompt or ExecPlan.

---

## Manager Actions

### Inject Specialized Behavior
Include role/format inline (no system prompt flag):
```bash
codex exec "ROLE: TRACER. FORMAT: TRACE file:line desc. TASK: <task>" \
  -s read-only --skip-git-repo-check -o trace.txt
```

### Specialized Agent Templates

**Tracer**
```
ROLE: TRACER. FORMAT: TRACE file:line desc. TASK: <task>
```

**Verifier**
```
ROLE: VERIFIER. Be skeptical. FORMAT: CHECK [name] PASS|FAIL reason. TASK: <task>
```

**Debugger**
```
ROLE: DEBUGGER. Trace paths, find failures. FORMAT: file:line symptom hypothesis. TASK: <task>
```

### Performance

| Metric | Typical Value |
|--------|---------------|
| Simple query | 4-6s |
| ExecPlan generation | 15-30s |
| ExecPlan execution | task-dependent |
| Tokens per query | 4-6k |

