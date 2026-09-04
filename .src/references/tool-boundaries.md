# Tool Boundaries

| Tool | Responsible for | Not responsible for |
|---|---|---|
| `init` | Initialize the project `.pensieve/` directory, seed default content, and produce first-round exploration input | Does not write business conclusions directly |
| `upgrade` | Fast-forward a clean source checkout; report when a Codex snapshot needs reinstall | Never resets history, migrates data, or grades project health |
| `migrate` | Copy legacy data, add only missing seeds, and optionally clean after a verified full backup | Never overwrites customized seeds or deletes legacy paths by default |
| `doctor` | Run data checks plus selected-client integration checks, then emit a fixed report | Does not modify business code or inspect another client's integration |
| `self-improve` | Create new entries under `short-term/` and update existing files in place | Does not replace init/migrate/doctor |
| `refine` | Refine the knowledge base through triage review and compression | New entries produced by compression go through short-term |
| `sync-instructions` | Write existing pipeline short routes into `CLAUDE.md` / `AGENTS.md` | Does not generate project summaries, inline full pipelines, or replace `.pensieve/` |

## Common redirects

| User request | Correct tool |
|---|---|
| "How do I install/reinstall Pensieve?" | Read `.src/references/skill-lifecycle.md` first, then run `init` |
| "Upgrade Pensieve" | `upgrade` |
| "How do I update Pensieve?" | Read `.src/references/skill-lifecycle.md` first, then run `upgrade` |
| "Migrate to v2" | `migrate` (copy-only default) |
| "Clean legacy paths" | `migrate --cleanup-legacy` after dry-run review |
| "Check whether the data has issues" | `doctor` |
| "Capture this experience" | `self-improve` |
| "Organize/deduplicate/compress/refine knowledge" | `refine` |
| "Write pipelines into CLAUDE.md/AGENTS.md" | `sync-instructions` with an explicit client target |
