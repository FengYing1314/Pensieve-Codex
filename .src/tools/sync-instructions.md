---
description: Synchronize conditional links to existing Pensieve pipelines into the explicitly selected client's project instruction file.
---

# Sync Instructions

Use when the user requests project instruction integration or its update. Missing integration reported by Doctor is a suggestion, not permission to write during an unrelated task. Follow [shared rules](../references/shared-rules.md).

Set `PENSIEVE_SKILL_ROOT` to the actual source or installed plugin root and bind the intended project and client. The existing interface remains:

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/sync-instructions.sh" --client codex --target codex
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/sync-instructions.sh" --client claude --target claude
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/sync-instructions.sh" --client both --target all
```

`agent` and `agents` remain aliases for `codex`; `--file` accepts explicit targets. Generic auto mode updates existing recognized instruction files only. Normal Codex operation does not update Claude files.

## Managed content

The managed block contains the heading and conditional paths for the supported pipeline files that actually exist:

```markdown
<!-- pensieve:instructions:start -->
## How To Use Pensieve

- When the user requests executing a Git commit: use `.pensieve/pipelines/run-when-committing.md`.
- When the user requests implementing a refactor: use `.pensieve/pipelines/run-when-refactoring.md`.
- When the user requests a code review within the supplied scope: use `.pensieve/pipelines/run-when-reviewing-code.md`.
<!-- pensieve:instructions:end -->
```

No internal workflow steps, architectural preferences, or automatic-capture authorization are copied into this block. Doctor checks the same existing route set, not customized pipeline bodies. No supported pipeline means no synchronization writes; do not automatically run init to create one.

## File safety

All targets are preflighted before any target or session-marker write. Only no markers or one ordered pair of standalone markers is accepted. Duplicate, nested, isolated, reversed, or inline markers fail with the affected path; do not guess how to repair user text.

Resolve and deduplicate target paths before checking their relationships. A target cannot also serve as another target's parent directory. Check directory write access only for targets whose candidate content differs; already synchronized files can remain in read-only directories.

Only the managed byte region is replaced. Preserve surrounding bytes, LF/CRLF convention, EOF newline state, ordinary permissions, and existing resolvable symlinks. Empty/new files use UTF-8/LF. Dangling links and non-regular targets are rejected. Repeated synchronization changes neither instruction content nor its timestamp; an entirely unchanged sync does not rewrite its session marker.

Before each atomic replacement, verify the target still matches its preflight snapshot. Preflight errors leave every target unchanged. A write-phase I/O failure can occur after earlier targets were written; report written and unwritten paths, never claim transaction-wide rollback or premature success. Recover only task-owned outputs from recorded originals, without overwriting later user changes.

After changed files are synchronized, allow the session-marker refresh at most 10 seconds. On POSIX systems, timeout terminates the maintenance process group so a child waiting for the marker lock cannot write later. Timeout, launch failure, or a nonzero exit produces one short warning; completed instruction updates remain successful. An unchanged sync does not launch marker maintenance.
