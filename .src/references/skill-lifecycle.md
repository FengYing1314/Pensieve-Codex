---
id: skill-lifecycle
type: knowledge
title: Pensieve Installation and Updates
status: active
created: 2026-03-06
updated: 2026-09-08
tags: [pensieve, install, update, operations, codex, claude]
---

# Pensieve Installation and Updates

Use this reference for Pensieve installation and lifecycle work. Explanations, recommendations, and reviews stay read-only; the commands below run only within the requested maintenance scope. Existing authorization remains valid for the same target and action.

The maintained repository is [FengYing1314/Pensieve-Codex](https://github.com/FengYing1314/Pensieve-Codex), branch `main`. For repository development, validation, and local Codex rebuilds, use the [maintainer guide](../../docs/maintaining.md).

## Client layouts

- Codex source checkout: a clean Git clone, commonly `$HOME/plugins/pensieve`
- Codex installed runtime: a marketplace-managed snapshot containing `.codex-plugin/`, `hooks/`, `skills/`, and `.src/`
- Claude Code skill: a clean Git clone, commonly `$HOME/.claude/skills/pensieve`
- Project data for every client: `<project>/.pensieve/`

The source/runtime location is replaceable. Project data is not: treat `.pensieve/` as user-owned data and never delete it during installation or upgrade.

## Codex installation

1. Clone `main` from the maintained repository into the intended source directory, commonly `$HOME/plugins/pensieve`.
2. Register its local path in a personal marketplace entry.
3. Run `codex plugin add pensieve@<marketplace>`.
4. Start a new task and review `/hooks`. Trust only the expected `SessionStart`, `SubagentStart`, and `PostToolUse Edit|Write` commands.
5. Change into the target project's directory, then invoke `$pensieve init` or run `bash "$PENSIEVE_SKILL_ROOT/.src/scripts/init-project-data.sh" --client codex`, with `PENSIEVE_SKILL_ROOT` set to the selected source checkout or installed plugin root.

Codex discovers the plugin's `hooks/hooks.json` by default. Hooks are optional: all seven tools remain available through `skills/pensieve` without Hook execution.

## Claude Code installation

```bash
git clone -b main https://github.com/FengYing1314/Pensieve-Codex.git "$HOME/.claude/skills/pensieve"
bash "$HOME/.claude/skills/pensieve/.src/scripts/install-hooks.sh"

cd <your-project>
bash "$HOME/.claude/skills/pensieve/.src/scripts/init-project-data.sh" --client claude
```

`install-hooks.sh` updates the Claude user settings. Projects without `.pensieve/` remain unaffected.

## Post-initialization verification

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-doctor.sh" --client <client> --strict
```

Doctor writes reports and derived project state, so run it only as part of authorized verification or maintenance. Core PASS conditions include valid structure, frontmatter, state, and graph data. Missing selected-client instruction integration is advisory by default. Add `--require-integration` only when installation policy requires that integration to be present.

## Updates

An upgrade request permits the selected source update and its agreed project maintenance; a question about upgrading does not execute either. Verify the source checkout's configured upstream and the project receiving reports before running the command. Upgrade accepts only a clean Git worktree and fast-forward history:

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-upgrade.sh" --client <client>
```

It never runs a hard reset. `--dry-run` validates the target and shows the planned pull without fetching or writing reports/state. `--skip-version-check` skips the pull but still writes reports/state; it is not a read-only check. If `git pull --ff-only` fails, inspect the branch state and resolve it within the user's authorization before retrying.

An installed Codex snapshot is not a source checkout. Point the installed tool at the clean clone, then reinstall the plugin:

```bash
bash "<installed-plugin-root>/.src/scripts/run-upgrade.sh" \
  --client codex --source-root "$HOME/plugins/pensieve"
codex plugin add pensieve@<marketplace>
```

Start a new task after reinstalling so Codex reloads skills and the current Hook definitions. Local source edits and cachebuster rebuilds use the [maintainer guide](../../docs/maintaining.md), rather than the clean-checkout upgrade command.

## Migration

```bash
# Zero-write preview
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-migrate.sh" --client <client> --dry-run

# Copy legacy data and keep the source
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-migrate.sh" --client <client>

# Optional, destructive only after complete verified backup
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-migrate.sh" --client <client> --cleanup-legacy
```

Migration never replaces an existing pipeline, maxim, or knowledge seed. Conflicting legacy data is written as a separate timestamped candidate. Unknown legacy files stay in place by default and are included in the full backup before explicit cleanup.

## Reinstallation and removal

Before changing an installation:

1. Confirm the exact source or installed snapshot path.
2. Preserve every project `.pensieve/` directory.
3. Preserve source-checkout changes before replacing a clone. Manage Codex snapshots through the plugin manager; do not edit, move, or remove cache directories by hand.
4. Install the replacement through the selected client's workflow and verify Skill discovery.
5. When project verification is included in the maintenance request, run Doctor for that project or an agreed temporary fixture.
6. For Codex, start a new task and review changed Hook hashes again.

Removing the plugin or Skill does not imply permission to remove project `.pensieve/` data.

## Hook capability mapping

| Purpose | Claude Code | Codex |
|---|---|---|
| Session health and due reminder | `SessionStart` | `SessionStart` |
| Subagent recall | `SubagentStart` | `SubagentStart` |
| Knowledge-state refresh | `PostToolUse Write/Edit/MultiEdit` | `PostToolUse Edit|Write` |

Both adapters call `.src/core/hook_runtime.py`; provider envelopes differ, semantic outcomes do not.

The Claude adapter still accepts the historical `PreToolUse Agent` envelope so existing installations degrade safely until `install-hooks.sh` is rerun. New installs use only native `SubagentStart` and do not grant tool permissions.
