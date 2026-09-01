# Market Intelligence v5.4 Entity Master

This patch replaces static ticker keyword matching with a resolver-backed entity layer.

## What This Solves

Before v5.4, a query like `PLTR` only matched text if a hard-coded keyword happened to be present. That meant the system could miss articles saying `Palantir Technologies` unless we manually fed that alias.

v5.4 adds a persisted entity master:

- `ticker`
- `cik`
- `legal_name`
- `common_name`
- `aliases`
- `domains`
- `exchange`
- `sector`
- `source`
- `confidence`
- `active`

The official backbone is SEC `company_tickers.json`, which maps ticker to CIK and legal company title. This gives us a market-wide base resolver without depending on fragile one-off alias lists.

## Files

- `src/backtester/intelligence/entity_resolver.py`
  - Loads `data/intelligence/entity_master.csv` or `ENTITY_MASTER_PATH`.
  - Resolves ticker, company name, common name, legal name, domains, and aliases.
  - Keeps a small static fallback so existing scripts do not break before the cache exists.
- `src/backtester/intelligence/provider_policy.py`
  - `query_relevance()` now delegates to the entity resolver.
  - Historical news collectors automatically get resolver-backed relevance.
- `src/backtester/intelligence/entity_extractor.py`
  - Evidence/claim extraction uses the same resolver.
- `scripts/build_entity_master.py`
  - Builds the CSV from SEC company tickers, local SEC JSON, source JSONL, and optional manual aliases.
- `scripts/resolve_entities.py`
  - Smoke-test utility.

## Build The Market-Wide Cache

One light SEC request:

`python scripts/build_entity_master.py --fetch-sec-company-tickers --sec-user-agent "$SEC_USER_AGENT" --out data/intelligence/entity_master.csv`

No-network local SEC JSON path:

`python scripts/build_entity_master.py --sec-company-tickers-json /path/to/company_tickers.json --out data/intelligence/entity_master.csv`

Fallback from already-collected source files:

`python scripts/build_entity_master.py --source-jsonl data/intelligence/historical/raw/sec_eval_2025_2026.jsonl --source-jsonl data/intelligence/historical/raw/news_eval_2025_2026_merged_full_scored.jsonl --out data/intelligence/entity_master.csv`

## Smoke Test

`ENTITY_MASTER_PATH=data/intelligence/entity_master.csv python scripts/resolve_entities.py --query PLTR --text "Palantir Technologies won a new government software contract."`

Expected behavior:

- `resolved_ticker=PLTR`
- matched terms include `Palantir` or `Palantir Technologies`
- score passes the default threshold

## Why This Matters

This is the bridge from "keyword search over tickers we fed it" to a market-wide security/entity master. It lets news ingestion, evidence scoring, and historical feature building understand that `PLTR`, `Palantir`, `Palantir Technologies Inc`, and the SEC CIK are the same entity.

The next step after this is point-in-time entity history: ticker changes, company renames, mergers, spin-offs, and inactive tickers.
