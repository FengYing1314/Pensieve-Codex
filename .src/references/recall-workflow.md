# Pensieve Recall Workflow

Use this provider-neutral workflow before broad project exploration.

1. Locate the nearest ancestor containing `.pensieve/`. If none exists, report that no Pensieve project memory is available and continue with ordinary exploration.
2. Read `.pensieve/state.md` when present, then inspect the generated graph at `.pensieve/.state/pensieve-user-data-graph.md` on demand.
3. Match the request against `knowledge/`, `decisions/`, `maxims/`, `pipelines/`, and `short-term/`:
   - reuse verified file locations, module boundaries, and call chains from `knowledge/`;
   - treat active `decisions/` and `maxims/` as settled constraints unless the user asks to revisit them;
   - follow a matching workflow from `pipelines/`;
   - treat `short-term/` as unpromoted evidence that still needs validation.
4. Read at most five likely entries. If the graph has no useful match, perform at most two targeted text searches under `.pensieve/` before returning to source inspection.
5. Stop when the question is answered, the budget is exhausted, or two searches add no useful evidence.

Return four compact sections when they add value: Known Information, Known Pitfalls, Recommended Path, and To Explore. Cite project-relative entry paths. Do not write memory during recall alone; use the Pensieve `self-improve` or `refine` workflow for changes.
