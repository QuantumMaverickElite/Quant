# Market Intelligence v3.1

Adds SEC EDGAR historical point-in-time filing collection.

## New Files

- `src/backtester/intelligence/sec_source_collector.py`
- `scripts/fetch_sec_intelligence_sources.py`

## Purpose

SEC filings are cleaner than news for historical ML training:

- deterministic filing dates
- reliable company/ticker mapping through CIK
- point-in-time company events
- no article relevance ambiguity

## Collected Fields

The collector writes historical intelligence JSONL records with:

- ticker/query
- SEC source metadata
- filing form
- filing date
- report date
- accession number
- primary document URL
- filing description/items when available
- raw SEC filing row

## Required User-Agent

SEC requests should identify the script/user.

Set:

```bash
export SEC_USER_AGENT="stock-backtester your-email@example.com"
```

or pass:

```bash
--user-agent "stock-backtester your-email@example.com"
```

## Smoke Test

```bash
python -m scripts.fetch_sec_intelligence_sources \
  --tickers PLTR \
  --start 2026-05-01 \
  --end 2026-05-28 \
  --forms 10-K 10-Q 8-K S-1 424B DEF\ 14A \
  --user-agent "stock-backtester your-email@example.com" \
  --out data/intelligence/historical/raw/sec_pltr_2026_05_smoke.jsonl
```

## Next Step

After SEC and GDELT both produce historical raw JSONL, build:

- `historical_event_feature_builder.py`
- rolling 1d/7d/30d point-in-time features
- joins to historical signal dates
