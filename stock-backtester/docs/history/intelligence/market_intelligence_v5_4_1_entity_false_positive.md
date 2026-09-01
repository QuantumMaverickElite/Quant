# Market Intelligence v5.4.1 Entity False-Positive Guard

v5.4 introduced the entity master. v5.4.1 tightens entity matching so market-wide scans do not overmatch short tickers or generic company names.

## Fixes

- Bare one-letter tickers no longer match ordinary words like `a`.
- Short ticker aliases now require exact uppercase text or a cashtag.
- Generic aliases such as `Technologies`, `Systems`, `Holdings`, or `Capital` are ignored when they appear alone.
- `resolve_text_to_entities()` now requires stronger evidence than a single weak alias.

## Expected Smoke

`ENTITY_MASTER_PATH=data/intelligence/entity_master.csv python scripts/resolve_entities.py --query PLTR --text "Palantir Technologies won a new government software contract."`

Expected:

- `resolved_ticker=PLTR`
- `matched_terms` includes `Palantir` and/or `Palantir Technologies`
- `text_entities` should not include unrelated short tickers like `A`
