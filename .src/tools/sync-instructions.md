---
description: Write the current project's existing Pensieve pipelines into a short-route block in the selected CLAUDE.md and/or AGENTS.md. Idempotent; does not overwrite user content.
---

# Sync Instructions Tool

> Tool boundaries: see `.src/references/tool-boundaries.md` | Shared rules: see `.src/references/shared-rules.md`

## Use when

- The user asks to write Pensieve pipelines into `CLAUDE.md`, `AGENTS.md`, `agent.md`, or another project-level agent instruction file
- The user wants the next agent to know which pipeline to use for commit / refactor / review requests
- The project already has `.pensieve/pipelines/`, but the entry instruction files lack short routes

This tool only writes short routes. It does not generate project summaries or inline full pipeline content.

## Failure fallback

- `.src/scripts/sync-instructions.sh` is missing: stop and report an incomplete skill installation
- `<project>/.pensieve/pipelines/` is missing: run `init` first
- Pensieve markers in the target file are unpaired: stop and ask the user to repair the markers manually

## Standard execution

Set `PENSIEVE_SKILL_ROOT` to the checkout or plugin root.

The default updates only the active client's instruction file. In generic mode it updates recognized files that already exist and refuses to create both implicitly:

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/sync-instructions.sh"
```

Client-specific targets:

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/sync-instructions.sh" --client codex --target codex
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/sync-instructions.sh" --client claude --target claude
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/sync-instructions.sh" --client both --target all
```

`agents` and `agent` remain compatibility aliases for `codex`.

## Written Content

The inserted block contains only one heading and short routes:

```markdown
## How To Use Pensieve

Use `.pensieve/` as the first source of architectural intent.

- `maxims/` are active engineering rules.
- `decisions/` are active project decisions.
- `knowledge/` explains boundary maps and debugging paths.
- `pipelines/` gives executable workflows.

Use these project pipelines directly when trigger words match; do not rediscover them through skills first.

- Commit requests (`commit`, `git commit`): use `.pensieve/pipelines/run-when-committing.md`. Check staged diff, decide whether reusable insight should be captured, then make atomic commits.
- Refactor requests (`refactor`, `large refactor`, `split code`): use `.pensieve/pipelines/run-when-refactoring.md`. Confirm the real problem, fix upstream data authority first, split large work into 2-3 user-visible steps, delete old paths when new paths work, and avoid compatibility/fallback branches.
- Review requests (`review`, `code review`, `inspect code`): use `.pensieve/pipelines/run-when-reviewing-code.md`. Start from git history and changed hot spots, verify candidate issues, and report only high-signal findings with evidence and file locations.
```
