# Maintaining this repository

Use this guide for changes to the Pensieve source checkout. The seven user-facing tool contracts remain in [`.src/tools/`](../.src/tools/); project knowledge remains in each project's `.pensieve/`. Neither this guide nor a stored workflow grants permission to commit, push, install, or modify a project.

## Repository map

| Area | Responsibility |
|---|---|
| `.codex-plugin/`, `hooks/`, `skills/` | Codex packaging, lifecycle registration, and two thin entrypoints |
| `SKILL.md`, `agents/` | Compatible Claude/general entrypoint and its UI metadata |
| `.src/core/`, `.src/scripts/` | Shared runtime and existing command launchers |
| `.src/tools/`, `.src/references/` | User workflow contracts and supporting specifications |
| `.src/templates/` | Defaults copied only when project data is missing |
| `.src/tests/support.py`, `.src/tests/fixtures/` | Shared isolated test support and paired client payloads |
| `.src/tests/test_*.py` | Contract, migration, upgrade, synchronization, and automatic-refresh tests |
| `.codex/skills/pensieve-sync-to-main/` | Explicit repository language-branch synchronization only |
| `docs/`, `CHANGELOG.md` | Repository maintenance, examples, current changes, and archived upstream history |

Keep existing public script paths and client adapters unless an explicit migration requires a change. The historical `run-hook.sh`, `explore-prehook.sh`, and `sync-project-skill-graph.sh` launchers still support existing Claude configurations. Root and Codex Skill metadata serve separate client entrypoints and are not redundant copies to delete.

## Local verification

From the repository root, run:

```bash
bash .src/scripts/check-repository.sh
```

The same entrypoint runs in CI on Python 3.8 and 3.12. It checks every Shell script, compiles Python into an automatically cleaned temporary directory, executes all standard-library tests, validates the four JSON manifests/schema files, and checks the diff. It does not install dependencies or run business services.

Choose an already installed interpreter when needed:

```bash
PYTHON_BIN=python3.12 bash .src/scripts/check-repository.sh
```

Test fixtures use disposable projects under `$HOME/.cache/pensieve-tests` by default. `PENSIEVE_TEST_TMPDIR` can select another writable test parent; avoid `/tmp` because production project-root validation intentionally rejects it. Do not weaken that guard for tests. Shared fixtures belong in `support.py`, so tests do not import another test module merely to obtain setup helpers.

A passing repository suite proves its exercised contracts, not every future agent behavior or native desktop Hook delivery. For instruction changes, use isolated, fresh tasks with saved inputs and file snapshots; report actual branches exercised and retain failed attempts separately from successful reruns.

## Optional official validators

When Codex's system `plugin-creator` and `skill-creator` skills are available, locate their current installation paths and additionally run:

- `plugin-creator/scripts/validate_plugin.py` against this checkout.
- `skill-creator/scripts/quick_validate.py` against the root Skill, `skills/pensieve`, `skills/pensieve-wand`, and any repository-maintenance Skill being changed.

These are external Codex tools, not dependencies supplied by this repository. Follow their current `SKILL.md` instructions; do not assume another developer has the same absolute paths.

## Updating a local Codex installation

Source edits do not change an already installed plugin snapshot. Preserve every project's `.pensieve/` data and use the official `plugin-creator` update flow:

1. Verify the configured local marketplace resolves `pensieve` to this checkout. Read its marketplace name with the official `read_marketplace_name.py` helper.
2. Finish the source change and relevant verification.
3. Run the official `update_plugin_cachebuster.py` helper against this checkout. Keep the shared `.src/manifest.json` version at the current base version; the plugin manifest may have one `+codex.<token>` build suffix. Replace the suffix instead of stacking it or changing the base just to invalidate a cache.
4. Recheck the final manifest and affected validation, then run `codex plugin add pensieve@<verified-marketplace>`.
5. Compare installed files with the final source and start a new task to verify discovered Skill paths and version. Review Hook trust through the client; never write trust records or edit cached source files by hand.

For a clean source checkout updated from its upstream branch, the existing `upgrade` command uses `git pull --ff-only`; see [the lifecycle guide](../.src/references/skill-lifecycle.md). Local uncommitted development changes use the official cachebuster/reinstall flow instead of bypassing upgrade's clean-worktree protection.

## Commit and push

The maintained repository is [FengYing1314/Pensieve-Codex](https://github.com/FengYing1314/Pensieve-Codex), with `main` as its default branch. An older remote URL may redirect here after the rename; inspect the actual remote and branch rather than assuming a remote name is correct. Keep upstream attribution and archived history distinct from this fork's release destination.

When the user requests publication, inspect status and the staged diff, include only the authorized change, run outstanding relevant checks, then commit and push to the verified destination. Existing authorization remains valid for that scope. Do not choose all staged files, force-push, change remotes, merge unrelated branches, or open an upstream PR merely because a maintenance workflow mentions those actions.

Use the current commit convention: a lowercase Conventional Commit type and an accurate summary. Record user-visible changes in `CHANGELOG.md` under `Unreleased`; upstream historical version labels are not this fork's version sequence. After pushing, verify the remote commit and inspect the corresponding CI result without treating an earlier run as evidence for a new commit.
