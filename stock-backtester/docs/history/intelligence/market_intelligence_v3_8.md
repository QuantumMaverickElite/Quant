# Market Intelligence v3.8

Purpose: diversify historical news inputs and make the ML/walk-forward/Monte Carlo workflow runnable unattended.

## What changed

- Added `scripts/merge_historical_sources.py`.
  - Merges multiple JSONL source files.
  - Dedupes by provider article id, then URL, then stable query/title/date hash.
- Added checkpoint-aware sentiment scoring controls to `scripts/score_historical_news_sentiment.py`.
  - Use `--nlp-device cpu` on small GPUs. The 4 GB GPU path can OOM with FinBERT.
  - Use `--checkpoint-every` so long scoring runs write partial output.
- Added `scripts/monte_carlo_walk_forward_predictions.py`.
  - Bootstraps out-of-sample walk-forward test dates.
  - Compares baseline, heuristic NLP, and walk-forward ML rankings.
- Added `scripts/run_intelligence_training_batch.py`.
  - Runs source merge, optional sentiment scoring, news feature build, calibration dataset build, walk-forward grid, and Monte Carlo grid.
  - Writes `manifest.csv` under the run directory after every step.

## Source Strategy

Do not rely on one source.

Recommended source order:

1. Finnhub news and recommendation trends.
   - Already produced a useful historical baseline.
   - Recommendation trends give analyst pressure.
2. Polygon or paid NewsAPI-style source if available.
   - Useful for broader headline coverage and source diversity.
3. SEC EDGAR.
   - Useful as a small formal-disclosure factor, not as the main sentiment source.
4. GDELT.
   - Useful as broad discovery only after strict relevance filtering and slow retry settings.
   - It should not be treated as a high-quality ticker-specific source by itself.
5. Alpha Vantage.
   - Free tier is too slow for the 50-ticker panel because of the daily request limit.

The important rule is point-in-time: every source record must have a `published_at` timestamp, and features only use records published on or before the signal date.

## Apply

From `~/projects/quant/stock-backtester`:

```bash
cp market_intelligence_v3_8_overlay/src/backtester/intelligence/historical_source_merge.py src/backtester/intelligence/historical_source_merge.py && cp market_intelligence_v3_8_overlay/src/backtester/intelligence/historical_news_sentiment.py src/backtester/intelligence/historical_news_sentiment.py && cp market_intelligence_v3_8_overlay/src/backtester/intelligence/historical_news_feature_builder.py src/backtester/intelligence/historical_news_feature_builder.py && cp market_intelligence_v3_8_overlay/src/backtester/intelligence/calibration_dataset.py src/backtester/intelligence/calibration_dataset.py && cp market_intelligence_v3_8_overlay/scripts/merge_historical_sources.py scripts/merge_historical_sources.py && cp market_intelligence_v3_8_overlay/scripts/score_historical_news_sentiment.py scripts/score_historical_news_sentiment.py && cp market_intelligence_v3_8_overlay/scripts/build_historical_news_features.py scripts/build_historical_news_features.py && cp market_intelligence_v3_8_overlay/scripts/monte_carlo_walk_forward_predictions.py scripts/monte_carlo_walk_forward_predictions.py && cp market_intelligence_v3_8_overlay/scripts/run_intelligence_training_batch.py scripts/run_intelligence_training_batch.py && cp market_intelligence_v3_8_overlay/docs/market_intelligence_v3_8.md docs/market_intelligence_v3_8.md
```

## Merge Existing Sources

If the Finnhub file is already sentiment-scored:

```bash
python -m scripts.merge_historical_sources --inputs data/intelligence/historical/raw/news_eval_2025_2026_finnhub_scored.jsonl --out data/intelligence/historical/raw/news_eval_2025_2026_merged_scored.jsonl
```

If more source files are added later, pass them all after `--inputs`.

## Overnight Training

Create the run directory first because shell redirection needs it before Python starts:

```bash
mkdir -p outputs/intelligence/training_runs/sec_news_grid_20260623
```

Use the already-scored Finnhub file and run the full walk-forward/Monte Carlo grid:

```bash
nohup python -m scripts.run_intelligence_training_batch --news-sources data/intelligence/historical/raw/news_eval_2025_2026_merged_scored.jsonl --work-dir outputs/intelligence/training_runs/sec_news_grid_20260623 --iterations 20000 --train-days-list 90 126 252 --embargo-days-list 10 20 --alpha-list 1 3 10 30 --model-types logistic ridge --min-train-rows-list 100 200 --keep-going > outputs/intelligence/training_runs/sec_news_grid_20260623/run.log 2>&1 &
```

If the source files have not been scored yet, add `--score-sentiment --nlp-device cpu`.

Monitor:

```bash
tail -f outputs/intelligence/training_runs/sec_news_grid_20260623/run.log
```

Check completed steps:

```bash
column -s, -t outputs/intelligence/training_runs/sec_news_grid_20260623/manifest.csv | less -S
```

## Interpreting Results

Primary outputs:

- `historical_news_merged.jsonl`
- `historical_news_features.parquet`
- `historical_panel_labeled_sec_news.parquet`
- `historical_intelligence_panel_sec_news.parquet`
- `*_summary.csv`
- `*_monte_carlo.csv`
- `manifest.csv`

Read the Monte Carlo files first. The minimum bar for accepting ML changes should be:

- positive `cash_ml_minus_baseline`
- positive `cash_ml_minus_heuristic`
- `prob_ml_beats_baseline` meaningfully above 0.50
- stable results across multiple train windows, alphas, and model types

If a configuration only wins once or only on top-N 50 where the ranking barely changes, treat it as noise.
