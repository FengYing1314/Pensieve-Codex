---
name: pensieve-sync-to-main
description: Synchronize explicitly requested Pensieve language branches into main. Use only for a requested language-branch sync; ordinary translation, repository cleanup, and release questions do not activate this workflow.
---

# Pensieve Language-Branch Sync

This repository-maintenance entry keeps its historical path and name. It applies only when the user explicitly requests synchronizing language branches. For general repository development, validation, and local builds, read the [maintainer guide](../../../docs/maintaining.md).

## Establish the requested integration

- Verify the actual repository, worktree changes, source ref, target ref, and any remote repository from the current request and Git evidence. The maintained repository is `FengYing1314/Pensieve-Codex`; a configured remote name alone does not establish the intended source or publication target.
- Do not assume that `zh` or `experimental` exists, select an upstream remote by default, or add/change remotes. If a material source, target, or integration decision is missing, resolve that decision before the dependent action.
- Existing authorization remains valid for the same action and target. Inspection or planning remains read-only; branch creation, merging, committing, pushing, and PR creation occur only within the authorization already provided. Do not ask again for already authorized steps.

## Preserve the requested content and history

- Compare the requested source and target before integrating. Keep unrelated work intact and limit a file-specific request to those files.
- When a branch merge is requested, preserve contributor history unless the user chooses another integration method. Resolve conflicts from the intended behavior and both sides' evidence; do not automatically prefer the source branch or use a blanket conflict-resolution strategy.
- For translation-only changes, preserve code behavior, identifiers, protocol/schema keys, executable paths, link targets, and intentionally multilingual tests. Follow the target branch's established documentation language; do not translate every Chinese string indiscriminately.
- Installation examples for this maintained repository use `https://github.com/FengYing1314/Pensieve-Codex` and `main`. Keep explicitly identified upstream historical references separate.

## Validate and deliver

- For implementation, use the relevant checks in the [maintainer guide](../../../docs/maintaining.md) and review the resulting diff. The repository validation entry is `bash .src/scripts/check-repository.sh` from the repository root.
- When committing is authorized, stage only the reviewed task paths and inspect the staged diff. A sync request does not authorize staging unrelated files.
- Push or open a PR only to the verified repository and branch authorized by the user. Do not default to an upstream PR or merge a PR without authorization for that action.
- On a rejected push or unresolved integration problem, inspect and report the cause. Continue supported resolution within the existing scope; do not automatically rebase, force-push, reset, or switch publication targets.
