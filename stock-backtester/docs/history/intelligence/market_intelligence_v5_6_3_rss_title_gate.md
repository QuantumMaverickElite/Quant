# Market Intelligence v5.6.3 — RSS Headline Entity Gate

This patch tightens RSS relevance after the v5.6.2 text-first filter.

## Why

Some ticker-scoped RSS feeds can return adjacent or broad-market stories. A row can still mention the ticker/company in feed metadata or description text even when the headline itself is about another company. For alpha/training inputs, that is too noisy.

## Behavior

RSS records now require entity evidence in the headline by default. Description/body matches remain in `raw.relevance_audit`, but cannot rescue a headline that does not name the canonical ticker/company.

New audit fields:

- `title_matched_terms`
- `title_relevance_score`
- `description_matched_terms`
- `description_relevance_score`
- `requires_title_entity`
- `title_entity_gate_pass`
- `pre_title_gate_relevance_score`

## CLI escape hatch

Use this only for manual exploration:

```bash
--allow-rss-body-only
```

Default is strict headline gating.

## Smoke

A fake Surf-Air-style row with only `PLTR` / `Palantir` in the description now gets `relevance_score=0.0` and fails the default RSS gate. A headline like `Palantir Stock Nears Fresh Low` still passes.
