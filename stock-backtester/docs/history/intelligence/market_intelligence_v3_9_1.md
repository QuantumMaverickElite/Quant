# Market Intelligence v3.9.1

Purpose: make historical news fetching resilient under strict provider rate limits.

## What changed

- `scripts/fetch_historical_news_sources.py` now fetches incrementally by provider/ticker.
- The output JSONL is written after each ticker.
- `--resume` skips provider/ticker pairs already marked complete in a sidecar state CSV.
- Empty batches are not marked complete by default, because they may be caused by 429 rate limits.
- Added fetch controls:
  - `--max-retries`
  - `--backoff-seconds`
  - `--timeout-seconds`
  - `--query-offset`
  - `--max-queries`
  - `--massive-sleep-seconds`
  - `--mark-empty-complete`

## Apply

From `~/projects/quant/stock-backtester`:

```bash
cp market_intelligence_v3_9_1_overlay/src/backtester/intelligence/historical_news_collector.py src/backtester/intelligence/historical_news_collector.py && cp market_intelligence_v3_9_1_overlay/scripts/fetch_historical_news_sources.py scripts/fetch_historical_news_sources.py && cp market_intelligence_v3_9_1_overlay/docs/market_intelligence_v3_9_1.md docs/market_intelligence_v3_9_1.md
```

## Safer Massive Fetch

Do not fetch all 50 tickers at once on a rate-limited key. Start with a chunk:

```bash
python -m scripts.fetch_historical_news_sources --providers massive_news --queries-file data/intelligence/historical/sec_eval_tickers.txt --start 2025-01-01 --end 2026-05-28 --limit 50 --query-offset 0 --max-queries 5 --massive-sleep-seconds 30 --max-retries 8 --backoff-seconds 60 --resume --out data/intelligence/historical/raw/news_eval_2025_2026_massive.jsonl
```

Then continue with the next chunk:

```bash
python -m scripts.fetch_historical_news_sources --providers massive_news --queries-file data/intelligence/historical/sec_eval_tickers.txt --start 2025-01-01 --end 2026-05-28 --limit 50 --query-offset 5 --max-queries 5 --massive-sleep-seconds 30 --max-retries 8 --backoff-seconds 60 --resume --out data/intelligence/historical/raw/news_eval_2025_2026_massive.jsonl
```

The sidecar state file defaults to:

```text
data/intelligence/historical/raw/news_eval_2025_2026_massive.jsonl.state.csv
```

Inspect it:

```bash
column -s, -t data/intelligence/historical/raw/news_eval_2025_2026_massive.jsonl.state.csv | tail -40
```

If a ticker keeps returning zero because it truly has no records, rerun with `--mark-empty-complete` for that chunk only.

## Current Interpretation

The 429 errors mean the adapter reached Massive, authenticated far enough to receive provider rate-limit responses, and was making valid requests. The issue is request pacing/quota, not the normalized schema.

Use chunked fetches first. If Massive still 429s on the first ticker after long backoff, that account/key likely has a daily/monthly cap or requires a paid tier for historical stock news.
