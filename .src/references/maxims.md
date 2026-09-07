# Maxims

Recorded engineering constraints with explicit applicability, evidence, and exceptions. Broad usefulness alone does not make a preference universally mandatory.

## Criteria for inclusion

Only entries that satisfy all of the following belong in `maxims/`:

1. Has a clear, supported scope and evidence
2. Distinguishes requirements from preferences and examples
3. Explains the concrete failure prevented and any necessary exceptions
4. Is explicitly adopted within its stated scope rather than inferred from a few observations

Project-specific trade-offs belong in `decisions/`; do not reclassify them merely to make them harder to override.

## Storage location

```text
<project>/.pensieve/maxims/
└── {one-sentence-conclusion}.md
```

One file per maxim.
During initialization, default entries are seeded from `.src/templates/maxims/`; afterwards users can freely modify them, and upgrades will not overwrite.

## Recommended format

```markdown
# {One-line Conclusion}

## One-line Conclusion
> {One actionable sentence}

## Guidance
- Rule 1
- Rule 2

## Boundaries
- When it does not apply

## Context Links (recommended)
- Based on: [[related decision or knowledge]]
- Leads to: [[related pipeline or decision]]
- Related: [[related maxim]]
```

## Rules

- `maxim` should remain scarce — do not stuff one-off preferences in here
- Links are recommended, but when sources exist they should be clearly stated
- `Based on` can only point to `knowledge/decision`
- `Leads to` can only point to `pipeline/decision`
- `Related` is suitable for pointing to parallel `maxim` entries
