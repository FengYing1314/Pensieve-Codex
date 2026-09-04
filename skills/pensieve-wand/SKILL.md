---
name: pensieve-wand
description: >-
  Recall relevant project knowledge, settled decisions, maxims, pitfalls, and
  pipelines from .pensieve/ before broad code exploration. Use to narrow a
  subagent's search scope and avoid repeating known work.
---

# Pensieve Wand for Codex

This is the Codex counterpart of the Claude Code `pensieve-wand` custom agent. Resolve the plugin root as two directories above this `SKILL.md`, then read and follow `../../.src/references/recall-workflow.md`.

Treat `.pensieve/` as project-owned data. Return a compact briefing with evidence paths; do not modify project memory unless the user also requested `self-improve` or `refine`.
