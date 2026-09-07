---
description: Review, merge, or promote project memory within an explicit maintenance request while preserving evidence and scope.
---

# Refine

Follow [shared rules](../references/shared-rules.md). Use only when the user requests memory organization, triage, deduplication, or refinement. A seven-day reminder or Doctor finding is not authorization to execute this workflow.

## Select the requested entries

For specified entries, inspect those entries and relevant links. For requested due-item triage, inspect due short-term entries. Read the whole library only for an explicitly requested whole-library review. Load category specifications only for the entries being changed.

For each candidate, determine whether it prevents repeated investigation or mistakes, has traceable evidence, overlaps another record, and still applies to the recorded time, project, and conditions. A historical observation or an intended project constraint is not false merely because today's code differs. Mark uncertainty for review rather than replacing it with a guess.

## Apply bounded changes

- Keep useful, supported entries. Promote a draft only after verifying its evidence and applicability under the user's maintenance request.
- Merge duplicates while preserving unique evidence, exceptions, and incoming links. Check destination collisions before moving a short-term entry; never overwrite a same-named long-term record.
- Delete only within the requested cleanup scope when the content is redundant or demonstrably invalid and useful evidence has been retained. Missing evidence alone does not authorize inventing a replacement fact.
- Compression must preserve the original applicability and provenance. Several APIs requiring idempotency establish a fact about those APIs, not a universal requirement for every external API. Do not turn examples or preferences into mandatory maxims.
- Do not change project decisions or rules as a side effect of factual deduplication. Such changes require a request covering those decisions or rules.

Use the existing metadata, directory, and link formats. Update links affected by authorized moves or merges. Refresh the affected project's `state.md` and `.state/` once after the authorized changes, with explicit target and client bindings as described in [self-improve](self-improve.md). Report changes and remaining uncertainty; a failed refresh does not authorize an extended repair workflow.
