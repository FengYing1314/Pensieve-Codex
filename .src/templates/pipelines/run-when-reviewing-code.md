---
id: run-when-reviewing-code
type: pipeline
title: Code Review Pipeline
status: active
created: 2026-02-11
updated: 2026-09-08
tags: [pensieve, pipeline, review]
name: run-when-reviewing-code
description: Review only the requested code scope with evidence; use history when relevant, report material issues, and keep code and memory unchanged.

stages: [tasks]
gate: auto
---

# Code Review Pipeline

Review is read-only, including project memory, generated state, dependency installation, and runtime services. Use the user's files, diff, commit, or PR as the scope. A pipeline or stale-index reminder does not authorize repair or capture.

## Workflow

1. Read the relevant diff and source, following callers or configuration only where needed to assess behavior. Consult history when it explains a specific concern; do not scan a fixed number of commits or merge unrelated hotspots into scope.
2. Verify material correctness, security, data-integrity, contract, and regression risks. Treat style references and complexity thresholds as optional context, never proof of a defect.
3. Report each supported finding with location, concrete trigger, impact, and practical remediation. State uncertainty or unavailable checks honestly; do not manufacture numerical confidence or filler findings.

When no material issue is established, say so and describe meaningful residual uncertainty. Missing optional history is not a blocker. Potential reusable knowledge may be mentioned in the report, but writing it requires a separate authorized maintenance or implementation-closeout task.

## Context Links

- Related: [[knowledge/taste-review/content]]
