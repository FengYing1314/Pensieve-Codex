---
name: pensieve
description: >-
  Retrieve and maintain project-local Pensieve knowledge. Use for relevant project
  memory lookup, explicitly requested maintenance, or enabled factual capture
  after implementation; route the seven existing lifecycle workflows.
---

# Pensieve for Codex

This is a thin Codex entry point. The shared implementation lives at the plugin root in `.src/`; do not copy it into this skill.

Resolve the plugin root as two directories above this `SKILL.md`, export it as `PENSIEVE_SKILL_ROOT`, and set `PENSIEVE_CLIENT=codex` for every command. Never fall back to a Claude installation path from this adapter.

Current requests and authorization control scope. Retrieval never authorizes maintenance. Decide whether the completed implementation established a reusable project fact before loading capture instructions; routine mechanical edits with no new fact skip capture and memory scans. For enabled factual closeout, read `../../.src/tools/self-improve.md`; create new draft facts only, without changing existing memory or Git state.

## Routing

- `init`: read and follow `../../.src/tools/init.md`.
- `upgrade`: read and follow `../../.src/tools/upgrade.md`.
- `migrate`: read and follow `../../.src/tools/migrate.md`.
- `doctor`: read and follow `../../.src/tools/doctor.md`.
- `self-improve`: read and follow `../../.src/tools/self-improve.md`.
- `refine`: read and follow `../../.src/tools/refine.md`.
- `sync-instructions`: read and follow `../../.src/tools/sync-instructions.md`; default to `--target codex`.
- Knowledge graph: read `<project>/.pensieve/.state/pensieve-user-data-graph.md` on demand.

Project user data remains in `<project>/.pensieve/`. Hooks only add reminders and automatic graph refresh; all seven tools remain fully usable when hooks are disabled or awaiting trust.
