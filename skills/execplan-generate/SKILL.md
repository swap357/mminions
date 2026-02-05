---
name: execplan-generate
description: Generate self-contained Codex ExecPlan markdown plans for complex engineering tasks. Use when a user asks for an ExecPlan, when work spans multiple files or risks, when autonomous execution needs explicit milestones, or when a read-only planning pass should happen before edits.
---

# ExecPlan Generate

## Overview

Create plans that another Codex run can execute without hidden context.
Keep plans minimal, concrete, and verifiable.

## Workflow

1. Define outcome.
   - State user-visible value in one sentence.
   - List hard constraints (sandbox, tooling, style, deadlines).
2. Capture context.
   - List relevant paths, commands, and repo conventions.
   - Record assumptions and unknowns explicitly.
3. Design milestones.
   - Split work into 2-6 milestones.
   - Make each milestone independently testable.
   - Keep ordering strict and avoid braided dependencies.
4. Write executable steps.
   - Provide exact commands and working directories.
   - Add expected output snippets for key commands.
   - Add fallback notes for risky operations.
5. Add validation.
   - Define validation for each milestone.
   - Define final integration validation.
6. Add operating notes.
   - Include `Surprises & Discoveries` and `Decision Log`.
   - Note expected generation latency: typically 15-30 seconds.
   - Note expected execution latency: task-dependent.

## Quality Gate

Reject the plan if any check fails:

- Missing repository paths or target files.
- Milestones that cannot be validated independently.
- Steps that require unstated context.
- Vague validation criteria (for example: "looks good").
- No section for discoveries and decisions.

## Output Contract

Return one Markdown ExecPlan using `references/execplan-template.md`.
Do not return extra prose outside the plan.

## Command Pattern

Use this headless pattern to generate plans:

```bash
codex exec "Create an ExecPlan for: <goal>. Include milestones, exact steps, and validation." -s read-only --skip-git-repo-check -o plan.md
```
