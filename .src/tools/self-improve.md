---
description: Capture reusable project knowledge under the authorized automatic or explicit maintenance scope.
---

# Self-Improve

Follow [shared rules](../references/shared-rules.md). Select the applicable mode before writing. Descriptions of how to use this tool are not requests to execute it.

## Automatic implementation closeout

Use only after completing and verifying an implementation task in a project whose user or applicable user-established project instructions explicitly enabled automatic factual capture. The policy is opt-in; installing Pensieve, finding `.pensieve/`, a commit request, or a stored pipeline alone does not enable it. Read-only tasks never enter this mode.

Decide from the completed task whether it established a reusable fact before loading further capture references or searching memory. Routine spelling, formatting, and mechanical edits with no new project fact skip this workflow and all memory scans; do not inspect unrelated code or tests to justify capture.

- Capture only new, evidenced project facts that will avoid repeated investigation: a verified root cause, a relevant entrypoint, or a concrete runtime boundary. Skip routine edits, transient progress, generic advice, speculation, and facts already recorded equivalently.
- Determine the actual owning project independently of the current directory. Do not borrow a parent or another project's memory store. If ownership, enablement, or the destination is uncertain, skip capture and continue delivery.
- Read [knowledge](../references/knowledge.md) and [short-term](../references/short-term.md), plus only relevant existing entries. Search both long-term and short-term originals, including aged entries omitted from the graph.
- Create only a new `short-term/knowledge/<unique-topic>/content.md` with `type: knowledge`, `status: draft`, and the existing required metadata. Include Source, Summary, Content, When to Use, and Invalidation Conditions. Never copy secrets, private data payloads, credentials, or environment values into a note.
- Never overwrite or append to an existing note. Choose a directory name and ID unused in either layer; add a date and then a numeric suffix when necessary. Create the file exclusively so a concurrent note is not replaced.
- For conflicting evidence, create a separate draft candidate with its own path and ID, explicitly identify the unresolved conflict, and link the original record. Do not silently replace a historical fact or promote a new decision. A hostname or observation date may distinguish historical context only when it is non-sensitive and needed.
- Link the actual original file, not just its topic directory. A knowledge wiki reference uses the full target-layer file path without `.md`, for example `[[knowledge/topic/content]]`, not `[[knowledge/topic]]`. Verify the referenced file exists and is the intended record. For an aged short-term original omitted from the graph, include a normal relative Markdown link to its actual short-term file so it remains directly readable; do not claim an unresolved graph link was verified.
- Do not write automatic `decisions`, `maxims`, or `pipelines`, even under short-term. All existing short-term and long-term files remain unchanged. No `git add`, commit, or background task is part of capture.

Before creation and refresh, resolve the authorized project, its `.pensieve/`, `short-term/knowledge/`, and `.state/` paths. They must belong to that project; stop this capture if a symlink or an inherited override redirects them elsewhere. Do not initialize or repair missing memory infrastructure automatically.

After a successful new note, refresh derived state once with explicit target bindings. Use the installed/source root selected for this task and the selected client; do not inherit another project's overrides:

```bash
PENSIEVE_PROJECT_ROOT="$pensieve_project" \
PENSIEVE_DATA_ROOT="$pensieve_project/.pensieve" \
PENSIEVE_STATE_ROOT="$pensieve_project/.pensieve/.state" \
PENSIEVE_SKILL_ROOT="$pensieve_source" \
PENSIEVE_CLIENT="$pensieve_client" \
bash "$pensieve_source/.src/scripts/maintain-project-state.sh" \
  --client "$pensieve_client" --project-only --event self-improve --note "Captured a verified project fact"
```

The automatic write allowance covers only the new note plus necessary `state.md` and `.state/` derived files, such as the graph and locks. `--project-only` validates existing project roots and output paths before writing; it never initializes missing roots, creates category directories, or updates a Claude client index. Hooks use this same restricted mode after recognized memory edits. If capture or refresh fails, report once and finish the original task; retain a successfully written note, do not retry maintenance, invoke Doctor, or repair the plugin. When nothing is captured, no refresh or status write is needed.

## Explicit memory maintenance

Use when the user asks to record, update, or maintain specified knowledge. This mode does not inherit the automatic allowance: follow the actual requested scope and preserve unrelated entries.

- Read only the corresponding category specification and the short-term rules when creating new data.
- New entries use their matching short-term category unless direct long-term placement was explicitly requested.
- Existing files may be edited in place only when their update is within the explicit maintenance request. The in-place exception never applies to automatic implementation closeout.
- Promotion, merging, or deletion follows [refine](refine.md) only when requested. Preserve evidence, applicability, and links.
- Refresh the affected project's derived state after authorized writes with explicit project/client bindings. Summarize written paths and any failed refresh without expanding into unrelated repair.
