---
description: Refresh a clean Pensieve source checkout using git pull --ff-only. Refuses dirty, non-Git, and non-fast-forward states and never resets local history.
---

# Upgrade Tool

> Tool boundaries: see `.src/references/tool-boundaries.md` | Shared rules: see `.src/references/shared-rules.md`

## Use when

- User requests a Pensieve upgrade
- Need to confirm version changes before and after upgrade

If the user first asks "how to update Pensieve", read `.src/references/skill-lifecycle.md` first, then run this tool.

This tool updates source checkouts only. An installed Codex snapshot must use `--source-root <checkout>` and then be reinstalled from its configured marketplace.

## Standard execution

Set `PENSIEVE_SKILL_ROOT` to the checkout or installed plugin root.

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-upgrade.sh"
```

Optional dry-run:

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-upgrade.sh" --dry-run
```

After upgrade, manually run:

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-doctor.sh" --strict
```

There is no force-reset fallback. If fast-forward fails, resolve the source checkout explicitly and retry.
