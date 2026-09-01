# Market Intelligence v5.5.1 — HTTP Request Budget + NewsAPI Error Clarity

This patch tightens the entity-aware historical news fetcher introduced in v5.5.

## Why

Entity search expansion can turn one canonical ticker query into several real provider calls. For example, `PLTR` may search both `PLTR` and `"Palantir Technologies"`. The old `--max-fetches` switch capped provider/query pairs, not the actual alias-expanded HTTP requests. That made small smokes less predictable.

NewsAPI plan/date errors also returned `HTTP 426 Upgrade Required`. Those should not be retried like transient transport errors.

## What changed

- Added `HttpRequestBudget`.
- Added `--max-http-requests` to `scripts/fetch_historical_news_sources.py`.
- The cap counts real HTTP attempts across providers, queries, aliases, pages, and retries.
- API keys/tokens are redacted in URL logs.
- HTTP 426 and other non-retryable HTTP errors print the response body and stop immediately.
- Existing `--max-fetches` remains, but is documented as provider/query-level only.

## Safe smoke

```bash
python scripts/fetch_historical_news_sources.py \
  --providers newsapi \
  --queries PLTR \
  --start 2026-05-01 \
  --end 2026-05-02 \
  --out /tmp/entity_search_preview.jsonl \
  --offline \
  --expand-entity-search \
  --entity-master data/intelligence/entity_master.csv \
  --max-search-aliases 2
```

## Tiny live smoke

```bash
python scripts/fetch_historical_news_sources.py \
  --providers newsapi \
  --queries PLTR \
  --start 2026-06-24 \
  --end 2026-06-25 \
  --out data/intelligence/historical/raw/newsapi_entity_search_recent_smoke.jsonl \
  --expand-entity-search \
  --entity-master data/intelligence/entity_master.csv \
  --max-search-aliases 2 \
  --max-http-requests 1 \
  --max-retries 0
```

Expected behavior: at most one real HTTP attempt. If NewsAPI returns 426, the response body is printed once and the alias-expanded second request is skipped by the budget.
