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
│   │   └── check-repository.sh     #   Repository validation entry
│   ├── tests/
│   │   ├── support.py             #   Shared isolated test fixtures
│   │   ├── fixtures/              #   Paired client Hook payloads
│   │   └── test_*.py              #   Contract and safety checks
│   ├── templates/
│   │   ├── agents/
│   │   ├── knowledge/
│   │   ├── maxims/
│   │   └── pipelines/
│   ├── references/
│   └── tools/
├── agents/                         #   Root Skill UI metadata
└── docs/maintaining.md             #   Repository maintenance and local rebuilds

Pensieve/.codex/skills/            # Repository-only maintenance skill; never seeded by init
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
├── state.md                        #   Generated lifecycle summary + graph reference
├── .gitignore                      #   Only ignores .state/
└── .state/                         #   Runtime artifacts (gitignored)

<project>/.claude/agents/           # Claude Code custom agents (seeded from templates on init)
└── pensieve-wand.md                #   Optional Claude knowledge retrieval agent
```

## Notes

- `.src/` is the only implementation source; root and Codex skills are thin client adapters
- The upgrade command requires a clean source checkout and uses `git pull --ff-only`; local development and rebuilds follow the [maintainer guide](../../docs/maintaining.md). Installed Codex snapshots are reinstalled from their source marketplace
- `.src/scripts/check-repository.sh` is the repository validation entry; `.src/tests/support.py` supplies isolated fixtures shared by the contract tests
- Repository-maintenance skills live under `Pensieve/.codex/skills/` and are not seeded into user projects. Default content installed into user projects lives under `.src/templates/`
- `SKILL.md` is a **static, tracked** file: the skill interface declaration; scripts do not generate it
- `state.md` is a **dynamic, generated** lifecycle summary at `<project>/.pensieve/state.md`; its Graph section points to `.state/pensieve-user-data-graph.md` instead of embedding the full graph. Refresh occurs only through authorized lifecycle maintenance or factual capture
- `maxims/decisions/knowledge/pipelines` are long-term user data, created locally after initialization
- `short-term/` is the staging area for new conclusions; it mirrors the long-term directory structure and uses `created` + 7-day TTL reminders for triage
- `.state/` lives inside `.pensieve/` and stores runtime artifacts such as doctor reports, migration backups, session markers, and generated graphs
- `maintain-project-state.sh` atomically replaces `state.md` only when content changes and serializes concurrent Hook updates
- `generate-user-data-graph.sh` / `doctor` output the graph to `.pensieve/.state/pensieve-user-data-graph.md` by default
- Resolve the system root from `.src/manifest.json`; the upgrade command additionally validates the complete Pensieve Git checkout
- Claude init can seed `.src/templates/agents/*.md` into `<project>/.claude/agents/`; Codex uses the packaged `skills/pensieve-wand` and never creates Claude client files
- `init` seeds `.src/templates/pipelines/run-when-*.md` into `<project>/.pensieve/pipelines/`
