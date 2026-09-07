---
id: run-when-refactoring
type: pipeline
title: Refactor Pipeline
status: active
created: 2026-04-27
updated: 2026-09-08
tags: [pensieve, pipeline, refactor]
name: run-when-refactoring
description: Implement a requested refactor within existing contracts; use evidence, proportional steps, and verification while preserving supported reliability mechanisms.

stages: [tasks]
gate: auto
---

# Refactor Pipeline

Use for an explicitly requested implementation refactor. Refactoring advice, review, or planning remains read-only. The current request defines scope and permitted behavior changes.

## Workflow

1. Establish the concrete problem and affected contract from relevant source and callers. Use project knowledge to locate evidence, not as permission to rewrite adjacent modules.
2. Identify data ownership and boundary checks. Prefer correcting an evidenced upstream defect where it is within scope; do not trust unvalidated external data or remove necessary downstream validation.
3. Implement the smallest coherent change. Break large work into as many verifiable increments as the task needs. Keep supported compatibility paths, fallbacks, idempotency, and recovery; remove replaced code only after checking callers and supported use cases.
4. Run focused checks for changed behavior, widening only for affected boundaries or unresolved failures. Compare the final diff with the requested outcome and report actual results.

If evidence or a dependency is unavailable, continue independent authorized work and explain the precise limitation. Do not force a redesign merely to remove a branch. A newly discovered need to change behavior outside scope requires a separate decision, not a silent expansion or premature stop of all work.

## Context Links

- Related: [[knowledge/taste-review/content]]
