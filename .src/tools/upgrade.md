---
description: Perform an authorized Pensieve source upgrade with git pull --ff-only; upgrade explanations and recommendations remain read-only.
---

# Upgrade Tool

Follow the [tool boundaries](../references/tool-boundaries.md) and [shared rules](../references/shared-rules.md).

## Use when

- The user requests executing a Pensieve upgrade for a known source checkout.
- For questions such as "how do I update Pensieve?", read [installation and lifecycle guidance](../references/skill-lifecycle.md) and explain the relevant procedure without running upgrade, Doctor, or state maintenance.

Version inspection is read-only. It does not require executing an upgrade; `--skip-version-check` still writes reports and project state.

This tool updates source checkouts only. An installed Codex snapshot must use `--source-root <checkout>` and then be reinstalled from its configured marketplace. Local edits and Codex cachebuster rebuilds follow the [maintainer guide](../../docs/maintaining.md).

The source must be the exact root of a clean, complete Pensieve Git checkout. Dirty, unrelated, nested, non-Git, and non-fast-forward states stop without resetting or rewriting history.

## Standard execution

Set `PENSIEVE_SKILL_ROOT` to the checkout or installed plugin root and select `PENSIEVE_CLIENT` for the actual client. Verify the checkout's configured upstream before updating. Run from the intended project directory: this command also writes upgrade reports and derived state for that project. Do not choose an unrelated project merely to run the tool.

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-upgrade.sh" --client "$PENSIEVE_CLIENT"
```

For a requested preview, `--dry-run` validates the selected checkout and shows the planned pull without fetching or writing reports/state:

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-upgrade.sh" --client "$PENSIEVE_CLIENT" --dry-run
```

After an authorized upgrade, run Doctor when verification of the selected project is included in the maintenance scope:

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-doctor.sh" --client "$PENSIEVE_CLIENT" --strict
```

Doctor writes reports and state; it is not part of a read-only explanation. Preserve existing authorization rather than asking again for already authorized steps. If fast-forward fails, report the checkout state and resolve it within the requested scope; do not reset, rebase, discard changes, or change remotes as a fallback.
