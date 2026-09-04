# Shared Rules

## Root Rules

1. `.src/` is the system files directory (located in the skill root); never write user data or runtime state into it.
2. `.pensieve/.state/` is the hidden runtime state directory; write reports, markers, caches, and other transient data here.
3. `.pensieve/{maxims,decisions,knowledge,pipelines}` are long-term user data directories; `.pensieve/short-term/{maxims,decisions,knowledge,pipelines}` is the short-term staging area. Bundled seeds become user-owned after creation and must not be force-aligned to templates.
4. `SKILL.md` in the skill root is a static, tracked file -- do not modify it.
5. Confirm before executing. Do not automatically run long workflows unless the user explicitly requests it.
6. Read the spec before writing data: before writing a maxim/decision/knowledge/pipeline, read the corresponding spec in `.src/references/`. New entries go into `short-term/` by default (see `.src/references/short-term.md`).
7. Keep links connected: every `decision/pipeline` must have at least one `[[...]]` link.
8. `[[...]]` links must not include the `short-term/` prefix -- always use the target-layer path (e.g. `[[decisions/foo]]`).
9. Respect client isolation: Codex may integrate with `AGENTS.md` but never Claude `MEMORY.md`; Claude may integrate with `CLAUDE.md`/Memory but does not require `AGENTS.md`; only explicit `both` enables both.
10. Hooks are optional. Every core workflow must remain executable manually.

## Path conventions

- System root: the checkout or installed plugin directory containing `.src/manifest.json`
- Tool specs: `.src/tools/*.md`
- Execution scripts: `.src/scripts/*.sh`
- Hidden templates: `.src/templates/**`
- Project user data: `<project>/.pensieve/`
- Hidden runtime state: `<project>/.pensieve/.state/**`
- Long-term user data:
  - `.pensieve/maxims/*.md`
  - `.pensieve/decisions/*.md`
  - `.pensieve/knowledge/*/content.md`
  - `.pensieve/pipelines/run-when-*.md`
- Short-term staging (mirrored structure):
  - `.pensieve/short-term/{maxims,decisions,knowledge,pipelines}/*`

## Semantic layers

- `knowledge` = IS (facts)
- `decision` = WANT (trade-offs)
- `maxim` = MUST (hard rules)
- `pipeline` = HOW (workflows)
- `short-term` = STAGING (staging area, flagged for review based on created + 7-day TTL)

## When to use migrate / upgrade

- Old paths or missing defaults: `migrate` (copy-only unless cleanup is explicit)
- Updating a clean source checkout: `upgrade`; reinstall Codex snapshots from their marketplace afterward
