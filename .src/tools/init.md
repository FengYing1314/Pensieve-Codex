---
description: Initialize the current project's .pensieve/ user data directory and provision seed files. Does not imply automatic capture enablement or a repository review. Idempotent; does not overwrite existing user data.
---

# Init Tool

> Tool boundaries: see `.src/references/tool-boundaries.md` | Shared rules: see `.src/references/shared-rules.md`

## Use when

- First time integrating Pensieve into a project
- User needs post-install initialization or post-reinstall default structure provisioning
- Missing base directories: `<project>/.pensieve/{maxims,decisions,knowledge,pipelines}`
- Missing default pipeline or taste-review knowledge

If the user first asks "how to install/reinstall Pensieve", read `.src/references/skill-lifecycle.md` and explain the setup. Execute this tool only when installation or initialization was requested.

Default pipeline seeds come from `.src/templates/pipelines/run-when-*.md`; do not scan `pipeline.*` files from the `.src/templates/` root.

## Failure fallback

- `.src/scripts/init-project-data.sh` missing: stop and report skill installation is incomplete
- Init script fails: output the failure reason, stop subsequent actions

## Standard execution

Set `PENSIEVE_SKILL_ROOT` to the checkout or plugin root. The client adapter sets `PENSIEVE_CLIENT`; direct callers should set it explicitly when auto-detection is ambiguous.

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/init-project-data.sh"
```

After initialization, report the created structure. Do not start a repository review, inspect commit history, or capture business conclusions unless that work was requested. State that Doctor writes derived state; run it only within the authorized setup/maintenance scope. Initialization alone does not enable automatic factual capture for future tasks.
