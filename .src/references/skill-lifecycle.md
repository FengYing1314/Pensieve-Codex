---
id: skill-lifecycle
type: knowledge
title: Pensieve Installation and Updates
status: active
created: 2026-03-06
updated: 2026-09-04
tags: [pensieve, install, update, operations, codex, claude]
---

# Pensieve Installation and Updates

Read this file before installing, initializing, updating, reinstalling, or uninstalling Pensieve.

## Client layouts

- Codex source checkout: a clean Git clone, commonly `$HOME/plugins/pensieve`
- Codex installed runtime: a marketplace-managed snapshot containing `.codex-plugin/`, `hooks/`, `skills/`, and `.src/`
- Claude Code skill: a clean Git clone, commonly `$HOME/.claude/skills/pensieve`
- Project data for every client: `<project>/.pensieve/`

The source/runtime location is replaceable. Project data is not: treat `.pensieve/` as user-owned data and never delete it during installation or upgrade.

## Codex installation

1. Clone the source repository.
2. Register its local path in a personal marketplace entry.
3. Run `codex plugin add pensieve@<marketplace>`.
4. Start a new task and review `/hooks`. Trust only the expected `SessionStart`, `SubagentStart`, and `PostToolUse Edit|Write` commands.
5. Invoke `$pensieve init`, or run `init-project-data.sh --client codex` from the source checkout.

Codex discovers the plugin's `hooks/hooks.json` by default. Hooks are optional: all seven tools remain available through `skills/pensieve` without Hook execution.

## Claude Code installation

```bash
git clone -b feat/codex-native-plugin https://github.com/FengYing1314/Pensieve.git "$HOME/.claude/skills/pensieve"
bash "$HOME/.claude/skills/pensieve/.src/scripts/install-hooks.sh"

cd <your-project>
bash "$HOME/.claude/skills/pensieve/.src/scripts/init-project-data.sh" --client claude
```

`install-hooks.sh` updates the Claude user settings. Projects without `.pensieve/` remain unaffected.

## Post-initialization verification

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-doctor.sh" --client <client> --strict
```

Core PASS conditions include valid structure, frontmatter, state, and graph data. Missing selected-client instruction integration is advisory by default. Add `--require-integration` only when installation policy requires that integration to be present.

## Updates

Upgrade accepts only a clean Git worktree and fast-forward history:

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-upgrade.sh" --client <client>
```

It never runs a hard reset. If `git pull --ff-only` fails, resolve the branch state explicitly before retrying.

An installed Codex snapshot is not a source checkout. Point the installed tool at the clean clone, then reinstall the plugin:

```bash
bash "<installed-plugin-root>/.src/scripts/run-upgrade.sh" \
  --client codex --source-root "$HOME/plugins/pensieve"
codex plugin add pensieve@<marketplace>
```

Start a new task after reinstalling so Codex reloads skills and the current Hook definitions.

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
3. Prefer moving the old installation to a timestamped backup over deleting it.
4. Install the replacement and verify Skill discovery.
5. Run Doctor for one temporary or non-production project.
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
