<div align="center">

# Pensieve

**A project knowledge base and workflow router for Codex, Claude Code, and skill-capable agents.**

[![GitHub Stars](https://img.shields.io/github/stars/FengYing1314/Pensieve-Codex?color=ffcb47&labelColor=black&style=flat-square)](https://github.com/FengYing1314/Pensieve-Codex/stargazers)
[![License](https://img.shields.io/badge/license-MIT-white?labelColor=black&style=flat-square)](LICENSE)

[Upstream project](https://github.com/kingkongshot/Pensieve) · [Upstream 中文 README](https://github.com/kingkongshot/Pensieve/blob/zh/README.md)

</div>

This repository maintains the Codex plugin and shared Claude Code runtime derived from the upstream Pensieve project. The upstream Chinese documentation describes its own release; use the installation instructions below for this repository.

Pensieve keeps project-owned memory in `.pensieve/` and loads only the relevant parts for a task. Knowledge, settled decisions, engineering maxims, reusable pipelines, and short-term conclusions remain independent of the client that uses them.

## Why use it

| Without Pensieve | With Pensieve |
|---|---|
| Re-explain project boundaries each session | Reuse cached locations, call chains, and module boundaries |
| Revisit settled trade-offs | Read active decisions and maxims before changing code |
| Reconstruct commit/review/refactor procedures | Follow executable project pipelines |
| Lose useful conclusions in chat history | Stage them in `short-term/`, then refine or promote them |
| Inject one large instruction file | Route to a small set of relevant entries on demand |

## Knowledge model

| Layer | Meaning | Answers |
|---|---|---|
| `maxims/` | MUST | Which engineering rules must not be violated? |
| `decisions/` | WANT | Why was this project trade-off selected? |
| `pipelines/` | HOW | How should a recurring workflow run? |
| `knowledge/` | IS | What verified facts, paths, and call chains are known? |
| `short-term/` | STAGING | Which new conclusions still need triage? |

Entries can link through `based-on`, `leads-to`, and `related`. Pensieve generates a project graph without copying the full graph into model context.

Example knowledge graphs:

<img src="docs/graph-overview.png" width="100%" alt="Pensieve knowledge graph overview" />
<img src="docs/graph-detail.png" width="100%" alt="Pensieve knowledge graph detail" />

## Seven tools

| Tool | Purpose |
|---|---|
| `init` | Create `.pensieve/` and install missing default seeds without overwriting existing data |
| `upgrade` | Update a clean source checkout with `git pull --ff-only` |
| `migrate` | Copy legacy data safely and optionally clean verified backups |
| `doctor` | Check project data and the selected client integration |
| `self-improve` | Capture reusable evidence-backed conclusions |
| `refine` | Triage, merge, promote, or remove staged knowledge |
| `sync-instructions` | Add compact routes to `AGENTS.md` and/or `CLAUDE.md` |

Detailed contracts live in [`.src/tools/`](.src/tools/) and [tool-boundaries.md](.src/references/tool-boundaries.md).

## Codex and Claude Code parity

The two clients use different native lifecycle events, but they share one semantic engine and the same `.pensieve/` format.

The packaging follows OpenAI's [Claude plugin migration guidance](https://developers.openai.com/plugins/guides/submit-claude-plugin), and the lifecycle adapter follows the current [Codex Hooks contract](https://learn.chatgpt.com/docs/hooks).

| Purpose | Claude Code | Codex | Shared result |
|---|---|---|---|
| Skill entry | Root `SKILL.md` | `skills/pensieve` | Same seven tool specifications under `.src/` |
| Session reminder | `SessionStart` | `SessionStart` | Same health/version/short-term decision |
| Subagent recall | native `SubagentStart` + optional `pensieve-wand` agent | native `SubagentStart` + `pensieve-wand` Skill | Same compact recall guidance |
| Edit synchronization | `Write/Edit/MultiEdit` file paths | `apply_patch` command paths | Same five data directories and state refresh |
| Instruction entry | `CLAUDE.md` + optional `MEMORY.md` | `AGENTS.md` + native Skill | Client-specific files never leak across modes |
| Hooks unavailable | Manual tools | Manual tools | Core workflow remains complete |

Healthy projects with no due short-term entries receive no session context. Projects without `.pensieve/` are ignored silently. Hook context is capped at 500 tokens.

## Installation

Prerequisites: `git`, `bash`, and Python 3.8+.

### Codex native plugin

Clone the maintained `main` branch as the source checkout used by a personal marketplace:

```bash
git clone -b main https://github.com/FengYing1314/Pensieve-Codex.git "$HOME/plugins/pensieve"
```

Register the existing checkout in your personal marketplace, preserving all existing entries. The default layout uses `~/.agents/plugins/marketplace.json` with the following entry; treat this as a format example, not a replacement for an existing marketplace file:

```json
{
  "name": "personal",
  "interface": {"displayName": "Personal"},
  "plugins": [
    {
      "name": "pensieve",
      "source": {"source": "local", "path": "./plugins/pensieve"},
      "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
      "category": "Productivity"
    }
  ]
}
```

Install and verify discovery:

```bash
codex plugin add pensieve@personal
codex plugin list
```

Start a new Codex task, open `/hooks`, review the bundled definitions, and trust them if they match this checkout. Pensieve does not bypass Codex hook trust. The plugin remains usable through `$pensieve` while hooks are untrusted or disabled.

Initialize a project through `$pensieve init`, or run the shared script directly:

```bash
cd <your-project>
PENSIEVE_CLIENT=codex PENSIEVE_SKILL_ROOT="$HOME/plugins/pensieve" \
  bash "$HOME/plugins/pensieve/.src/scripts/init-project-data.sh" --client codex
```

### Claude Code skill

The root Skill entry and historical Hook script paths remain compatible. The installer uses Claude's native `SubagentStart`; rerunning it removes only legacy Pensieve `PreToolUse Agent` entries and preserves unrelated hooks:

```bash
git clone -b main https://github.com/FengYing1314/Pensieve-Codex.git "$HOME/.claude/skills/pensieve"
bash "$HOME/.claude/skills/pensieve/.src/scripts/install-hooks.sh"

cd <your-project>
bash "$HOME/.claude/skills/pensieve/.src/scripts/init-project-data.sh" --client claude
```

### Generic skill-capable clients

Clone to the client-specific skill directory, set `PENSIEVE_SKILL_ROOT`, and pass `--client generic`. Hooks are optional; run state maintenance manually after edits.

## Client isolation

Commands accept `--client auto|codex|claude|both|generic`. `agents` and `agent` remain compatibility aliases for `codex` where an instruction target is accepted.

- `codex` reads or writes `AGENTS.md` integration only and never creates Claude `MEMORY.md`.
- `claude` reads or writes `CLAUDE.md` and an optional Claude routing index only; `.pensieve/` remains the sole knowledge authority and it does not require `AGENTS.md`.
- `both` explicitly enables both integrations.
- `generic` checks only provider-neutral project data.
- `auto` uses Hook-provided identity, client environment variables, and the installation path; Codex's native `PLUGIN_ROOT` wins its `CLAUDE_PLUGIN_ROOT` compatibility alias, and auto never silently chooses `both`.

Doctor reports missing client integration as `SHOULD_FIX` by default. Use `--require-integration` when CI or rollout policy requires it to fail:

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-doctor.sh" --client codex --strict
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-doctor.sh" --client codex --strict --require-integration
```

`sync-instructions` defaults to the selected client's file. Use explicit targets when repairing a particular integration:

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/sync-instructions.sh" --client codex --target codex
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/sync-instructions.sh" --client claude --target claude
```

## Safe migration

Migration copies legacy files and reports conflicts by default. Existing seeds are project-owned and are never replaced merely because they differ from bundled templates. Legacy files, including unknown files, remain in place.

```bash
# Preview with zero filesystem writes
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-migrate.sh" --client codex --dry-run

# Copy data; keep legacy locations
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-migrate.sh" --client codex

# Optional cleanup: back up every legacy location, verify the copy, then delete
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-migrate.sh" --client codex --cleanup-legacy
```

If any backup fails verification, cleanup stops before deleting legacy data.

## Safe upgrades

The upgrade tool requires the exact root of a clean, structurally valid Pensieve Git checkout and only runs `git pull --ff-only`. Dirty, unrelated, nested, non-Git, and non-fast-forward states stop safely; it never resets or rewrites local history.

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-upgrade.sh" --client claude
```

An installed Codex plugin snapshot is not updated in place. Update its source checkout, reinstall from the configured marketplace, then start a new task:

```bash
PENSIEVE_SKILL_ROOT="<installed-plugin-root>" \
  bash "<installed-plugin-root>/.src/scripts/run-upgrade.sh" \
  --client codex --source-root "$HOME/plugins/pensieve"
codex plugin add pensieve@personal
```

## Architecture

```text
Pensieve/
├── .codex-plugin/plugin.json       # Codex native manifest
├── hooks/hooks.json                # Codex default-discovered lifecycle hooks
├── skills/
│   ├── pensieve/                   # Thin seven-tool Codex router
│   └── pensieve-wand/              # Thin Codex recall skill
├── SKILL.md                        # Preserved Claude/general Skill entry
├── .src/                           # One shared implementation and specification source
└── .codex/skills/pensieve-sync-to-main/
                                     # Repository-maintenance skill; not a user runtime entry

<project>/.pensieve/
├── maxims/
├── decisions/
├── knowledge/
├── pipelines/
├── short-term/{maxims,decisions,knowledge,pipelines}/
├── state.md                        # Atomically updated only when content changes
└── .state/                         # Reports, marker, lock, and generated graph (gitignored)
```

Concurrent Hook updates serialize through a project lock. `state.md`, marker JSON, reports, and the knowledge graph use temporary-file replacement so interrupted or overlapping Hook processes cannot leave partial content.

## Capture and synchronization boundaries

Automatic implementation closeout is opt-in per maintained project. It adds only new draft facts under `short-term/knowledge/`, with evidence, applicability, and invalidation conditions. Existing notes, long-term rules, decisions, and Git state are unchanged. Read-only tasks never run memory maintenance, even when a Hook reports stale state. Explicit maintenance follows the requested scope; seven-day reminders never delete or promote entries.

Routine mechanical edits with no new project fact skip capture instructions and memory scans. Automatic capture and recognized memory-edit Hooks use `maintain-project-state.sh --project-only`, which checks existing project roots and derived output paths before writing, ignores other-project Hook environment overrides, and leaves Claude routing indexes unchanged. Explicit lifecycle maintenance without this flag retains its client-index updates. A rejected or failed automatic refresh reports once without starting Doctor or repair.

Instruction synchronization writes only conditional links to existing supported pipelines. Every target is preflighted before writing; malformed markers cause zero target writes. Managed-region replacement preserves surrounding bytes, LF/CRLF, EOF newline style, ordinary permissions, and resolvable symlinks. Write-phase errors report partial progress; synchronization is not a cross-file transaction.

The shared runtime version stays at `1.4.0`; local Codex builds may append one `+codex.<token>` to the plugin version. Check the final manifest after adding a cachebuster. An existing Doctor marker does not prove a newly installed build has passed behavioral verification.

## Verification

Run the same repository checks used by CI:

```bash
bash .src/scripts/check-repository.sh
```

The script checks every Shell script, compiles Python into a temporary directory, runs the standard-library tests, validates the JSON manifests and schema, and checks the diff. Set `PYTHON_BIN` to an existing interpreter when testing another supported version. A live Claude Code binary is not required for contract tests.

See [Maintaining this repository](docs/maintaining.md) for the test layout, optional official plugin/skill validators, local build refresh, and release checks. See [CHANGELOG.md](CHANGELOG.md) for current changes and archived upstream history.

## License

MIT
