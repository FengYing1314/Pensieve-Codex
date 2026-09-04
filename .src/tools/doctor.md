---
description: Scan the current project's .pensieve/ data and only the selected client integration, then emit a fixed-format report without modifying project knowledge or business code.
---

# Doctor Tool

> Tool boundaries: see `.src/references/tool-boundaries.md` | Shared rules: see `.src/references/shared-rules.md` | Directory conventions: see `.src/references/directory-layout.md`

## Use when

- Rechecking after init
- Rechecking after upgrade
- Confirming MUST_FIX is cleared after migration
- Suspected drift in the graph, frontmatter, directory structure, or the selected client's short routes

## Standard execution

Set `PENSIEVE_SKILL_ROOT` to the checkout or plugin root.

```bash
bash "$PENSIEVE_SKILL_ROOT/.src/scripts/run-doctor.sh" --strict
```

Doctor only maintains:

- `<project>/.pensieve/state.md` (lifecycle state + Graph)
- Runtime graph output such as `.pensieve/.state/pensieve-user-data-graph.md`
- Claude auto memory only when `--client claude|both` is selected

Doctor reports missing or drifted selected-client integration as `SHOULD_FIX` by default. Add `--require-integration` to promote those findings to `MUST_FIX`. Codex never checks Claude files; Claude never requires `AGENTS.md`.

Bundled seeds become project-owned after initialization. Missing seeds are reported, but customized seed content is not treated as damage.

It does not modify business code.
