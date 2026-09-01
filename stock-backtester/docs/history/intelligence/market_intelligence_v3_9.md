# Market Intelligence v3.9

Purpose: expand historical news coverage while reducing duplicate article risk and speeding up Monte Carlo evaluation.

## What changed

- Added `massive_news` provider support to `scripts/fetch_historical_news_sources.py`.
  - Uses `MASSIVE_API_KEY` or `--massive-key`.
  - Normalizes Massive stock news into the same JSONL schema used by Finnhub, NewsAPI, Alpha Vantage, Polygon, and SEC-derived sources.
- Improved source merge/dedupe.
  - Canonicalizes URLs by removing common tracking query parameters.
  - Soft-dedupes by normalized `query + title + published day`.
  - Can write `historical_news_merge_audit.csv`.
  - Can filter low-relevance records with `--min-relevance-score`.
- Improved feature fallback for provider-native sentiment.
  - FinBERT `raw.model_sentiment_score` remains preferred.
  - Alpha Vantage provider sentiment, Finnhub analyst pressure, and Polygon/Massive `insights.sentiment` can be used when FinBERT has not scored a record.
- Vectorized walk-forward Monte Carlo.
  - The old implementation looped through every bootstrap iteration in Python.
  - v3.9 samples all bootstrap date indices with NumPy and computes vectorized means.
- Added `scripts/summarize_intelligence_training_run.py`.
  - Ranks all `*_monte_carlo.csv` files from a run directory.

## Apply

From `~/projects/quant/stock-backtester`:

```bash
cp market_intelligence_v3_9_overlay/src/backtester/intelligence/historical_news_collector.py src/backtester/intelligence/historical_news_collector.py && cp market_intelligence_v3_9_overlay/src/backtester/intelligence/historical_source_merge.py src/backtester/intelligence/historical_source_merge.py && cp market_intelligence_v3_9_overlay/src/backtester/intelligence/historical_news_feature_builder.py src/backtester/intelligence/historical_news_feature_builder.py && cp market_intelligence_v3_9_overlay/scripts/fetch_historical_news_sources.py scripts/fetch_historical_news_sources.py && cp market_intelligence_v3_9_overlay/scripts/merge_historical_sources.py scripts/merge_historical_sources.py && cp market_intelligence_v3_9_overlay/scripts/build_historical_news_features.py scripts/build_historical_news_features.py && cp market_intelligence_v3_9_overlay/scripts/monte_carlo_walk_forward_predictions.py scripts/monte_carlo_walk_forward_predictions.py && cp market_intelligence_v3_9_overlay/scripts/run_intelligence_training_batch.py scripts/run_intelligence_training_batch.py && cp market_intelligence_v3_9_overlay/scripts/summarize_intelligence_training_run.py scripts/summarize_intelligence_training_run.py && cp market_intelligence_v3_9_overlay/docs/market_intelligence_v3_9.md docs/market_intelligence_v3_9.md
```

## Fetch More Sources

Massive:

```bash
python -m scripts.fetch_historical_news_sources --providers massive_news --queries-file data/intelligence/historical/sec_eval_tickers.txt --start 2025-01-01 --end 2026-05-28 --limit 100 --sleep-seconds 1 --out data/intelligence/historical/raw/news_eval_2025_2026_massive.jsonl
```

NewsAPI, if the account supports the requested historical range:

```bash
python -m scripts.fetch_historical_news_sources --providers newsapi --queries-file data/intelligence/historical/sec_eval_tickers.txt --start 2025-01-01 --end 2026-05-28 --limit 100 --sleep-seconds 1 --out data/intelligence/historical/raw/news_eval_2025_2026_newsapi.jsonl
```

Polygon, if the account/key is still under Polygon naming:

```bash
python -m scripts.fetch_historical_news_sources --providers polygon_news --queries-file data/intelligence/historical/sec_eval_tickers.txt --start 2025-01-01 --end 2026-05-28 --limit 100 --sleep-seconds 1 --out data/intelligence/historical/raw/news_eval_2025_2026_polygon.jsonl
```

## Merge With Dedupe Audit

```bash
python -m scripts.merge_historical_sources --inputs data/intelligence/historical/raw/news_eval_2025_2026_finnhub_scored.jsonl data/intelligence/historical/raw/news_eval_2025_2026_massive.jsonl --out data/intelligence/historical/raw/news_eval_2025_2026_merged.jsonl --audit-csv outputs/intelligence/training_runs/news_merge_audit.csv --min-relevance-score 0.25
```

Score merged news if needed:

```bash
INTELLIGENCE_NLP_DEVICE=cpu python -m scripts.score_historical_news_sentiment --input data/intelligence/historical/raw/news_eval_2025_2026_merged.jsonl --out data/intelligence/historical/raw/news_eval_2025_2026_merged_scored.jsonl --backend finbert --batch-size 16 --checkpoint-every 250 --nlp-device cpu
```

## Faster Test Run

Use a smaller grid first:

```bash
mkdir -p outputs/intelligence/training_runs/sec_news_grid_fast
nohup python -m scripts.run_intelligence_training_batch --news-sources data/intelligence/historical/raw/news_eval_2025_2026_merged_scored.jsonl --work-dir outputs/intelligence/training_runs/sec_news_grid_fast --iterations 5000 --train-days-list 90 126 --embargo-days-list 10 20 --alpha-list 3 10 --model-types logistic --min-train-rows-list 100 --min-relevance-score 0.25 --keep-going > outputs/intelligence/training_runs/sec_news_grid_fast/run.log 2>&1 &
```

Then summarize:

```bash
python -m scripts.summarize_intelligence_training_run --run-dir outputs/intelligence/training_runs/sec_news_grid_fast --out outputs/intelligence/training_runs/sec_news_grid_fast/all_monte_carlo_ranked.csv
```

## Quality Rules

- Do not add a source just because it is free.
- Require ticker relevance, a usable publication timestamp, and stable source identity.
- Always merge/dedupe before feature building.
- Prefer FinBERT sentiment when available; use provider sentiment as fallback or auxiliary signal.
- Treat SEC as formal disclosure context, not a replacement for broad news and analyst sentiment.
