# Market Intelligence v3.0.1

Adds the first historical point-in-time source collector.

v3.0.1 adds GDELT retry/backoff handling so HTTP 429 rate limits do not crash the whole run.

## New Files

- `src/backtester/intelligence/historical_source_collector.py`
- `scripts/fetch_historical_intelligence_sources.py`

## Provider v1

The first provider is GDELT DOC API article discovery.

This collector stores:

- `query`
- provider
- source/domain
- title
- URL
- published/seen timestamp
- fetched timestamp
- language/country metadata
- raw provider payload

## Why This Matters

ML training needs historical features that would have been known at the signal date.

The collector is designed to support point-in-time windows:

- 1 day
- 7 days
- 30 days

Those windows can later be aggregated into ticker/date event features and joined to historical strategy signals.

## Limitation

This does not scrape full article bodies. It stores article discovery metadata and titles/snippets. That is intentional for the first pass because it avoids brittle scraping and terms-of-service problems.

For richer historical training, evaluate licensed/paid historical news APIs or allowed full-text sources.

## Example

```bash
python -m scripts.fetch_historical_intelligence_sources \
  --provider gdelt \
  --queries PLTR QQQ MARKET \
  --start 2026-05-01 \
  --end 2026-05-28 \
  --window-days 7 \
  --max-records-per-query-window 10 \
  --sleep-seconds 2 \
  --max-retries 5 \
  --backoff-seconds 10 \
  --out data/intelligence/historical/raw/gdelt_pltr_qqq_market_2026_05.jsonl
```
