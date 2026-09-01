# Market Intelligence v3.6: Historical News and Analyst Sources

This patch starts the historical sentiment layer.

## What it adds

- `src/backtester/intelligence/historical_news_collector.py`
- `src/backtester/intelligence/historical_news_feature_builder.py`
- `src/backtester/intelligence/calibration_dataset.py`
- `scripts/fetch_historical_news_sources.py`
- `scripts/build_historical_news_features.py`

## Providers

The collector supports:

- `alpha_vantage`: ticker news and sentiment
- `finnhub_news`: ticker/company news
- `finnhub_recommendations`: analyst recommendation trends
- `newsapi`: broad article search
- `polygon_news`: ticker news metadata

API keys are read from:

- `ALPHA_VANTAGE_API_KEY`
- `FINNHUB_API_KEY`
- `NEWSAPI_KEY`
- `POLYGON_API_KEY`

## First recommended source

Start with Finnhub if available:

`python -m scripts.fetch_historical_news_sources --providers finnhub_news finnhub_recommendations --queries-file data/intelligence/historical/sec_eval_tickers.txt --start 2025-01-01 --end 2026-05-28 --limit 100 --sleep-seconds 1 --out data/intelligence/historical/raw/news_eval_2025_2026_finnhub.jsonl`

If Alpha Vantage is available:

`python -m scripts.fetch_historical_news_sources --providers alpha_vantage --queries-file data/intelligence/historical/sec_eval_tickers.txt --start 2025-01-01 --end 2026-05-28 --limit 200 --out data/intelligence/historical/raw/news_eval_2025_2026_alpha_vantage.jsonl`

## Build features

For one source file:

`python -m scripts.build_historical_news_features --news-sources data/intelligence/historical/raw/news_eval_2025_2026_finnhub.jsonl --signals outputs/intelligence/calibration/historical_panel_labeled_sec.parquet --features-out outputs/intelligence/historical/news_features_historical_panel.parquet --joined-out outputs/intelligence/calibration/historical_panel_labeled_sec_news.parquet --windows 1 7 30 90`

Then build the calibration panel:

`python -m scripts.build_intelligence_calibration_dataset --labeled-signals outputs/intelligence/calibration/historical_panel_labeled_sec_news.parquet --out outputs/intelligence/calibration/historical_intelligence_panel_sec_news.parquet`

Then walk-forward:

`python -m scripts.walk_forward_intelligence_calibration --dataset outputs/intelligence/calibration/historical_intelligence_panel_sec_news.parquet --target-col success_10d --return-cols next_5d_return next_10d_return --predictions-out outputs/intelligence/calibration/walk_forward_predictions_sec_news.parquet --summary-out outputs/intelligence/calibration/walk_forward_summary_sec_news.csv --train-days 252 --test-days 5 --step-days 5 --embargo-days 20 --min-train-rows 200`

## Feature columns

The feature builder creates point-in-time columns such as:

- `news_count_7d`
- `news_sentiment_mean_30d`
- `news_sentiment_weighted_30d`
- `news_positive_count_30d`
- `news_negative_count_30d`
- `analyst_recommendation_count_90d`
- `analyst_pressure_latest_90d`

`calibration_dataset.py` now includes `news_*` and `analyst_*` as trainable feature prefixes.

## Bias controls

- Only use records with provider timestamps.
- Join features only where `published_at <= signal_date`.
- Do not scrape current versions of old article pages and pretend they are historical snapshots.
- Do not join current NLP/event snapshots to old dates.
- Analyst data can be provider-plan dependent; verify that returned dates are real historical periods before treating them as point-in-time.
