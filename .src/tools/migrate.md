---
description: Migration tool. Copies legacy user data into the current structure without overwriting project-owned seeds. Legacy cleanup is separate, explicit, and backup-gated.
---

# Migrate Tool

> Tool boundaries: see `.src/references/tool-boundaries.md` | Shared rules: see `.src/references/shared-rules.md`

## Use when

- Migrating from v1 (project-level install) to v2 (user-level system + project-level data)
- Doctor reports a missing default seed
- Need to fill in directory structure without replacing customized files

Default seeds are copied only when missing. A content difference is treated as project customization, not drift. Historical `pipeline.run-when-*` names are normalized only while copying legacy data.

## Standard execution

Set `PENSIEVE_SKILL_ROOT` to the checkout or plugin root.

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-migrate.sh" --client auto
```

Optional dry-run:

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-migrate.sh" --client auto --dry-run
```

Dry-run performs zero writes. Normal migration copies and reports but retains every legacy path. Only use cleanup after reviewing the plan:

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-migrate.sh" --client auto --cleanup-legacy
```

Cleanup starts only after every legacy path, including unknown files, has a complete verified backup. A backup failure stops before deletion.
