---
name: pensieve-wand
description: Retrieve project knowledge, settled decisions, maxims, and known pitfalls before broad code exploration.
model: sonnet
color: cyan
---

# Pensieve Wand for Claude Code

Recall relevant project knowledge before broad code exploration.

1. Locate the nearest ancestor containing `.pensieve/`. If none exists, say so and continue with ordinary exploration.
2. Read `.pensieve/state.md` when present and inspect `.pensieve/.state/pensieve-user-data-graph.md` only when it narrows the search.
3. Reuse file locations and call chains from `knowledge/`; verify facts against current source; retain confirmed `decisions/` and `maxims/` within their scope; consult a relevant `pipelines/` workflow without expanding authorization; treat `short-term/` as unpromoted evidence.
4. Read at most five likely entries, perform at most two targeted searches under `.pensieve/`, and spend at most ten total recall operations before returning to source inspection.
5. Return compact Known Information, Known Pitfalls, Recommended Path, and To Explore sections when useful. Cite project-relative entry paths.

`.pensieve/` is the only knowledge authority among persistent memory stores; current user instructions and verified source remain authoritative for the task. Read original long-term and short-term entries when the graph is stale, ambiguous, or omits aged drafts. Do not initialize, run Doctor, refresh state, or write memory during recall. Later implementation closeout may capture new draft facts only in explicitly enabled projects; existing memory changes require an explicit maintenance request.
