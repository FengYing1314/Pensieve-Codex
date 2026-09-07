# Short-Term

`short-term/` is the staging area for new knowledge. Entries created by `self-improve` land here by default.

## Workflow

1. `self-improve` creates an entry -> writes to `short-term/{type}/`
2. Each entry carries a `created` date; it is considered expired after 7 days by default
3. Expired entries trigger reminders via session hook / doctor / commit pipeline
4. The user decides whether to promote (`mv` to the long-term directory) or delete

## Storage location

`short-term/` mirrors the long-term directory structure:

```text
<project>/.pensieve/short-term/
├── maxims/
├── decisions/
├── knowledge/
└── pipelines/
```

File naming follows the same convention as the corresponding long-term directory (e.g. `decisions/{date}-{statement}.md`).

## Link rules

`[[...]]` links must **not** include the `short-term/` prefix:

```markdown
- Based on: [[decisions/2026-03-16-foo]]     ✅
- Based on: [[short-term/decisions/2026-03-16-foo]]  ❌
```

When the graph resolver processes files inside short-term it strips the prefix, sharing node IDs with long-term files. Knowledge references include the file component: `[[knowledge/topic/content]]`. Verify the actual original file when adding a reference. Aged short-term entries can be omitted from the graph; use a normal relative Markdown file link for direct access to such an original, rather than treating a missing graph node as proof that the source does not exist.
On promote you only need to `mv` the file -- zero reference updates required.

## TTL rules

- Based on the `created` date + 7 days (schema.json `short_term.default_ttl_days`)
- Used for reminders only; files are never moved or deleted automatically
- Files whose frontmatter tags include `seed` skip the TTL check

## When to skip short-term

- Explicitly requested maintenance of an existing long-term file: edit within that requested scope. Automatic implementation closeout never uses this exception.
- The user explicitly requests writing directly to a long-term directory

Automatic capture creates new draft knowledge only. Existing short-term entries are not rewritten to update dates or content. Use unique directory names and IDs across both layers for conflicting candidates; inspect original files because the graph can omit aged short-term entries.
