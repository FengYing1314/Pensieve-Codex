# Directory Layout

Pensieve separates client-installed system code from project-owned data.

## Two anchor points

- **System root** (source checkout or installed plugin snapshot): shared `.src/` and client entry points
- **Project data** (`<project>/.pensieve/`): independent per project, can be version-controlled

## Layout

```text
Pensieve/                           # Source checkout / packaged plugin root
├── .codex-plugin/plugin.json       #   Codex native manifest
├── hooks/hooks.json                #   Codex native lifecycle hooks
├── skills/
│   ├── pensieve/                   #   Codex seven-tool router
│   └── pensieve-wand/              #   Codex recall workflow
├── SKILL.md                        #   Claude/general static routing entry
├── .src/                           #   System scripts, templates, specs (tracked)
│   ├── core/
│   ├── scripts/
│   ├── templates/
│   │   ├── agents/
│   │   ├── knowledge/
│   │   ├── maxims/
│   │   └── pipelines/
│   ├── references/
│   └── tools/
└── agents/                         #   root Skill UI metadata

<project>/.codex/skills/            # Project-level Codex skill (only for maintaining this repository)
└── pensieve-sync-to-main/
    ├── SKILL.md
    └── agents/
        └── openai.yaml

<project>/.pensieve/                # Project-level (per-project, can be version-controlled)
├── maxims/                         #   Engineering maxims (long-term)
├── decisions/                      #   Architecture decisions (long-term)
├── knowledge/                      #   Cached exploration results (long-term)
├── pipelines/                      #   Reusable workflows (long-term)
├── short-term/                     #   Staging area for new conclusions (mirrors long-term structure)
│   ├── maxims/
│   ├── decisions/
│   ├── knowledge/
│   └── pipelines/
├── state.md                        #   Dynamic: lifecycle state + knowledge graph (generated)
├── .gitignore                      #   Only ignores .state/
└── .state/                         #   Runtime artifacts (gitignored)

<project>/.claude/agents/           # Claude Code custom agents (seeded from templates on init)
└── pensieve-wand.md                #   Knowledge retrieval agent (dual-system decision)
```

## Notes

- `.src/` is the only implementation source; root and Codex skills are thin client adapters
- Source checkouts update only through a clean `git pull --ff-only`; installed Codex snapshots are reinstalled from their source marketplace
- Project-level maintenance skills live under `<project>/.codex/skills/`; default content seeded into user projects lives under `.src/templates/`
- `SKILL.md` is a **static, tracked** file: the skill interface declaration; scripts do not generate it
- `state.md` is a **dynamic, generated** file at `<project>/.pensieve/state.md`, refreshed by `init/doctor/migrate/upgrade/self-improve/sync`
- `maxims/decisions/knowledge/pipelines` are long-term user data, created locally after initialization
- `short-term/` is the staging area for new conclusions; it mirrors the long-term directory structure and uses `created` + 7-day TTL reminders for triage
- `.state/` lives inside `.pensieve/` and stores runtime artifacts such as doctor reports, migration backups, session markers, and generated graphs
- `maintain-project-state.sh` atomically replaces `state.md` only when content changes and serializes concurrent Hook updates
- `generate-user-data-graph.sh` / `doctor` output the graph to `.pensieve/.state/pensieve-user-data-graph.md` by default
- Any directory containing `.src/manifest.json` is a valid system root
- Claude init can seed `.src/templates/agents/*.md` into `<project>/.claude/agents/`; Codex uses the packaged `skills/pensieve-wand` and never creates Claude client files
- `init` seeds `.src/templates/pipelines/run-when-*.md` into `<project>/.pensieve/pipelines/`
