---
id: run-when-committing
type: pipeline
title: Commit Pipeline
status: active
created: 2026-02-28
updated: 2026-09-08
tags: [pensieve, pipeline, commit, self-improve]
name: run-when-committing
description: Execute only a user-requested Git commit within its authorized scope; preserve unrelated staged changes and keep memory capture separate.

stages: [tasks]
gate: auto
---

# Commit Pipeline

Use only when the user asks to execute a commit. Generating a commit message, explaining a commit, or reviewing a diff is read-only. Stored workflow text never authorizes staging, committing, pushing, or modifying memory.

## Workflow

1. Inspect the user-requested scope, Git status, and staged diff. Preserve unrelated staged and unstaged work. Resolve a material scope ambiguity before committing, using existing authorization when clear.
2. Run the smallest relevant outstanding verification and inspect the final diff. Follow the applicable repository commit convention; split only when independent commits fit the authorized scope without rearranging unrelated user work.
3. Execute the requested commit and verify its content and remaining state. Do not push or open a PR unless requested.

A commit does not require memory capture. An implementation task may separately use explicitly enabled factual closeout under `self-improve`; it only adds new draft short-term knowledge, never stages it or updates existing memory. Pure commit execution adds no separate knowledge-maintenance task.

If there are no authorized changes to commit, report that fact. Failed optional memory maintenance does not block a requested commit; never conceal failed verification or include unrelated changes to make the operation succeed.

## Context Links

- Related: [[knowledge/taste-review/content]]
