---
name: pensieve
description: >-
  Retrieve and maintain project-local Pensieve knowledge. Use for relevant project
  memory lookup, explicitly requested maintenance, or enabled factual capture
  after implementation; route the seven existing lifecycle workflows.
---

# Pensieve

Route requests within the current task and existing authorization. Retrieval is read-only. Decide whether the completed implementation established a reusable project fact before loading capture instructions; routine mechanical edits with no new fact skip capture and memory scans. Automatic capture otherwise requires explicit project enablement and follows `.src/tools/self-improve.md`.

Resolve the repository root containing `.src/manifest.json` as `PENSIEVE_SKILL_ROOT`. Pass `--client auto|codex|claude|both|generic` when the caller or requested integration is known; `auto` must never enable both clients implicitly. Hooks are optional acceleration and must not be required for any core tool.

## Routing
- Init: Initialize project data when requested; this does not enable automatic capture or start a code review. Tool spec: `.src/tools/init.md`.
- Upgrade: Refresh Pensieve skill source code in the global git clone. Tool spec: `.src/tools/upgrade.md`.
- Migrate: Copy legacy data safely; clean old locations only when explicitly requested. Tool spec: `.src/tools/migrate.md`.
- Doctor: Scan project data and only the selected client integration. Tool spec: `.src/tools/doctor.md`.
- Self-Improve: Capture new short-term facts under an enabled policy, or perform explicitly requested memory updates. Tool spec: `.src/tools/self-improve.md`.
- Refine: Refine the knowledge base with triage review and compression. Tool spec: `.src/tools/refine.md`.
- Sync Instructions: Write existing pipeline short routes into the selected `CLAUDE.md` and/or `AGENTS.md`. Tool spec: `.src/tools/sync-instructions.md`.
- Graph View: Read `<project-root>/.pensieve/.state/pensieve-user-data-graph.md`.

## Project Data
Project-level user data is stored in `<project-root>/.pensieve/`.
See `.pensieve/state.md` for the current project's lifecycle state; see `.pensieve/.state/pensieve-user-data-graph.md` for the knowledge graph (read on demand).
