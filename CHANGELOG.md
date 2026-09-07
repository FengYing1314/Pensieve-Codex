# Changelog

## Unreleased

### Changed

- Require explicit project opt-in for automatic factual capture; preserve existing short-term and long-term memory and skip routine edits with no new facts.
- Keep review, planning, recall, and commit-message requests read-only; remove fixed history scans and overbroad workflow rules.
- Use project-only refresh for automatic capture and memory-edit Hooks, preserving explicit Claude lifecycle integration.
- Point installation instructions and plugin metadata to `FengYing1314/Pensieve-Codex` on `main`; separate repository maintenance guidance from runtime tool specifications.
- Centralize test support and use one repository check command in local instructions and CI.

### Fixed

- Reject redirected output paths, destructive hard-link writes, and missing graph generators before automatic state writes.
- Terminate maintenance process groups on timeout instead of allowing late child-process writes.
- Preflight all instruction targets, reject conflicting target paths, and preserve unchanged files without requiring write permission.
- Preserve managed-block boundaries, LF/CRLF and EOF style, permissions, and client isolation; report write-phase partial progress.
- Validate a stable shared version with one optional Codex build suffix and check each Shell script individually.
- Link conflict candidates to the actual original knowledge files, including aged short-term sources omitted from the graph.

### Maintenance

- Remove unused seed-content comparison code, empty internal loop templates, and an unreferenced QR image; preserve supported compatibility launchers.
- Keep upstream language synchronization opt-in and bound to the requested repository, branches, and files.

## v1.4.0 — Codex Native Plugin and Cross-Client Parity

### Added

- Native Codex plugin manifest at `.codex-plugin/plugin.json`
- Default-discovered Codex lifecycle hooks for `SessionStart`, `SubagentStart`, and `PostToolUse Edit|Write`
- Thin Codex skills `pensieve` and `pensieve-wand`, both backed by the root `.src` implementation
- Shared Hook semantic engine and paired Claude/Codex contract fixtures
- `PENSIEVE_CLIENT=auto|codex|claude|both|generic` with `agent` / `agents` Codex aliases
- `doctor --require-integration`, `migrate --cleanup-legacy`, and `sync-instructions --target codex`
- Standard-library tests and a Python 3.8/3.12 GitHub Actions matrix

### Changed

- Healthy sessions with no due short-term entries inject no context; all Hook guidance remains below 500 tokens
- Codex updates only Codex integration state and never creates Claude `MEMORY.md`
- Doctor grades selected-client integration as `SHOULD_FIX` unless explicitly required
- Bundled seeds become project-owned after creation; customization is not treated as corruption
- State, marker, reports, and graph outputs use atomic replacement; Hook-driven state maintenance is serialized
- Project detection prefers the nearest `.pensieve/` and supports non-Git projects and Unicode paths
- Claude recall uses native `SubagentStart`; the legacy `PreToolUse Agent` envelope remains a no-permission compatibility path
- Instruction sync defaults to the active client, preserves existing file permissions, and skips unchanged writes
- Claude's optional wand agent treats `.pensieve/` as the sole knowledge authority instead of creating a second agent-memory store

### Safety

- Migration copies and reports by default; legacy deletion requires `--cleanup-legacy` and a fully verified backup
- Migration dry-run performs zero writes
- Upgrade refuses dirty/non-Git checkouts and only uses `git pull --ff-only`; hard-reset fallback was removed
- Installed Codex snapshots direct upgrades to a clean source checkout followed by marketplace reinstallation
- Upgrade validates the exact Pensieve checkout root; migration conflict copies use collision-safe names

## Upstream history

[Archived upstream v2 migration notes](docs/history/upstream-v2.md) use a separate version history. They are retained as historical documentation, not current installation or migration instructions.
