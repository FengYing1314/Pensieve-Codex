# Pipelines

A pipeline describes a recurring workflow whose order or verification boundaries materially improve execution. Use knowledge for factual maps and decisions for project choices; do not turn every task into a pipeline.

Store existing workflows at `<project>/.pensieve/pipelines/run-when-*.md`. Initialization seeds the three supported workflows; project copies remain user data and are not overwritten on upgrades.

Use the existing frontmatter fields `id`, `type`, `title`, `status`, `created`, `updated`, `tags`, and `description`; every pipeline needs a relevant `[[...]]` context link. Keep the description short and discriminate execution requests from explanation, review, or planning.

Describe the real outcome, necessary ordering, applicable verification, and how to handle unavailable evidence. Number steps only when order matters; choose the number of steps from the task, not a fixed template. Detailed background may be linked on demand instead of loaded before every action.

Current user intent and authorization control execution. Trigger words are discovery hints, not permission. A workflow must not introduce commits, memory updates, deployments, broad reviews, or new architecture outside the requested scope. Preserve supported compatibility, validation, recovery, and user-visible contracts.

Verification should examine observable behavior and evidence. Do not impose arbitrary confidence scores, code-size thresholds, universal prohibitions, or repeated approval gates. Missing optional context should lead to a bounded fallback, not early abandonment of authorized work.
