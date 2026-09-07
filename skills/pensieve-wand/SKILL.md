---
name: pensieve-wand
description: >-
  Recall relevant project knowledge, settled decisions, maxims, pitfalls, and
  pipelines from .pensieve/ before broad code exploration. Use to narrow a
  subagent's search scope and avoid repeating known work.
---

# Pensieve Wand for Codex

This is the Codex counterpart of the Claude Code `pensieve-wand` custom agent. Resolve the plugin root as two directories above this `SKILL.md`, then read and follow `../../.src/references/recall-workflow.md`.

Treat `.pensieve/` as project data, not proof of write authorization. Recall is read-only, including stale indexes. Return a compact briefing with evidence paths; later implementation closeout may use an explicitly enabled automatic factual policy, while existing memory changes require explicit maintenance.
