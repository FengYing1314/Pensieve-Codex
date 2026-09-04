---
name: pensieve
description: >-
  Project knowledge base and workflow router. knowledge/ caches explored file
  locations, module boundaries, and call chains for reuse; decisions/maxims are
  established architecture decisions and coding standards to follow, not
  relitigate; pipelines are reusable workflows; short-term/ stages new
  conclusions until promotion or deletion. Use self-improve after completing
  work to capture new insights. Provides seven tools: init, upgrade, migrate,
  doctor, self-improve, refine, and sync-instructions.
---

# Pensieve

Route user requests to the correct tool. When in doubt, confirm first.

Resolve the repository root containing `.src/manifest.json` as `PENSIEVE_SKILL_ROOT`. Pass `--client auto|codex|claude|both|generic` when the caller or requested integration is known; `auto` must never enable both clients implicitly. Hooks are optional acceleration and must not be required for any core tool.

## Routing
- Init: Initialize the current project user-data directory and seed files. Tool spec: `.src/tools/init.md`.
- Upgrade: Refresh Pensieve skill source code in the global git clone. Tool spec: `.src/tools/upgrade.md`.
- Migrate: Copy legacy data safely; clean old locations only when explicitly requested. Tool spec: `.src/tools/migrate.md`.
- Doctor: Scan project data and only the selected client integration. Tool spec: `.src/tools/doctor.md`.
- Self-Improve: Extract reusable conclusions and write them into user data. Tool spec: `.src/tools/self-improve.md`.
- Refine: Refine the knowledge base with triage review and compression. Tool spec: `.src/tools/refine.md`.
- Sync Instructions: Write existing pipeline short routes into the selected `CLAUDE.md` and/or `AGENTS.md`. Tool spec: `.src/tools/sync-instructions.md`.
- Graph View: Read `<project-root>/.pensieve/.state/pensieve-user-data-graph.md`.

## Project Data
Project-level user data is stored in `<project-root>/.pensieve/`.
See `.pensieve/state.md` for the current project's lifecycle state; see `.pensieve/.state/pensieve-user-data-graph.md` for the knowledge graph (read on demand).
