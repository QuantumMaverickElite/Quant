# Market Intelligence v5.2 - Provider Policy and Safer News Filtering

This overlay adds a lightweight source policy layer around historical news collection and merging.

## What Changed

- `src/backtester/intelligence/provider_policy.py`
  - Defines provider usage permissions, minimum relevance thresholds, and conservative request intervals.
  - Marks GDELT as discovery-only by default and not allowed for ML training.
  - Marks Reddit as not allowed for backtesting or ML training.
  - Marks NewsAPI as not allowed for ML training by default because free/dev usage is not a clean training assumption.
  - Adds ticker/company aliases such as `PLTR -> Palantir`, `MSFT -> Microsoft`, and `NVDA -> Nvidia`.

- `src/backtester/intelligence/historical_news_collector.py`
  - Replaces literal ticker-only relevance with alias-aware relevance scoring.
  - Adds provider policy metadata to fetched records.
  - Keeps the existing fetcher interfaces intact.

- `src/backtester/intelligence/historical_source_merge.py`
  - Adds optional merge-time source policy filtering.
  - Can filter sources by intended usage: `live_scoring`, `backtesting`, `ml_training`, or `storage`.

- `scripts/fetch_historical_news_sources.py`
  - Adds `--offline`.
  - Adds `--usage`.
  - Adds `--max-fetches`.
  - Applies provider minimum sleeps unless `--ignore-provider-policy` is set.

- `scripts/merge_historical_sources.py`
  - Adds `--apply-source-policy`.
  - Adds `--usage`.

## Apply

From the repo root:

```bash
cp market_intelligence_v5_2_policy_overlay/src/backtester/intelligence/provider_policy.py src/backtester/intelligence/provider_policy.py
cp market_intelligence_v5_2_policy_overlay/src/backtester/intelligence/historical_news_collector.py src/backtester/intelligence/historical_news_collector.py
cp market_intelligence_v5_2_policy_overlay/src/backtester/intelligence/historical_source_merge.py src/backtester/intelligence/historical_source_merge.py
cp market_intelligence_v5_2_policy_overlay/scripts/fetch_historical_news_sources.py scripts/fetch_historical_news_sources.py
cp market_intelligence_v5_2_policy_overlay/scripts/merge_historical_sources.py scripts/merge_historical_sources.py
cp market_intelligence_v5_2_policy_overlay/docs/market_intelligence_v5_2_provider_policy.md docs/market_intelligence_v5_2_provider_policy.md
python -m compileall -q src/backtester/intelligence scripts/fetch_historical_news_sources.py scripts/merge_historical_sources.py
```

## Safe Commands During Long Runs

Do not make network calls:

```bash
python scripts/fetch_historical_news_sources.py \
  --providers massive_news \
  --queries PLTR \
  --start 2026-01-01 \
  --end 2026-06-25 \
  --out data/intelligence/historical/raw/smoke.jsonl \
  --offline
```

One tiny capped fetch:

```bash
python scripts/fetch_historical_news_sources.py \
  --providers finnhub_news \
  --queries PLTR \
  --start 2026-06-01 \
  --end 2026-06-25 \
  --limit 5 \
  --max-fetches 1 \
  --usage backtesting \
  --out data/intelligence/historical/raw/finnhub_smoke.jsonl
```

Merge only sources allowed for ML training:

```bash
python scripts/merge_historical_sources.py \
  --inputs data/intelligence/historical/raw/*.jsonl \
  --out data/intelligence/historical/raw/news_merged_ml_allowed.jsonl \
  --apply-source-policy \
  --usage ml_training \
  --audit-csv outputs/intelligence/news_merge_policy_audit.csv
```

## Notes

This does not re-enable GDELT as a normal alpha feed. GDELT remains useful for candidate discovery, but it should be confirmed by higher-quality sources before it influences training or sizing.
