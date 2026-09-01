# Market Intelligence v3.7: Historical News Sentiment Scoring

This patch closes the gap from v3.6: Finnhub news gives article coverage, but not article sentiment.

## What it adds

- `src/backtester/intelligence/historical_news_sentiment.py`
- `src/backtester/intelligence/historical_news_feature_builder.py`
- `scripts/score_historical_news_sentiment.py`

## Workflow

Score historical Finnhub news:

`python -m scripts.score_historical_news_sentiment --input data/intelligence/historical/raw/news_eval_2025_2026_finnhub.jsonl --out data/intelligence/historical/raw/news_eval_2025_2026_finnhub_scored.jsonl --backend finbert --batch-size 32`

If GPU memory is tight, use CPU:

`INTELLIGENCE_NLP_DEVICE=cpu python -m scripts.score_historical_news_sentiment --input data/intelligence/historical/raw/news_eval_2025_2026_finnhub.jsonl --out data/intelligence/historical/raw/news_eval_2025_2026_finnhub_scored.jsonl --backend finbert --batch-size 16`

Fast fallback:

`python -m scripts.score_historical_news_sentiment --input data/intelligence/historical/raw/news_eval_2025_2026_finnhub.jsonl --out data/intelligence/historical/raw/news_eval_2025_2026_finnhub_scored.jsonl --backend heuristic`

Then rebuild features using the scored file:

`python -m scripts.build_historical_news_features --news-sources data/intelligence/historical/raw/news_eval_2025_2026_finnhub_scored.jsonl --signals outputs/intelligence/calibration/historical_panel_labeled_sec.parquet --features-out outputs/intelligence/historical/news_features_historical_panel_scored.parquet --joined-out outputs/intelligence/calibration/historical_panel_labeled_sec_news_scored.parquet --windows 1 7 30 90`

Then rebuild calibration and walk-forward:

`python -m scripts.build_intelligence_calibration_dataset --labeled-signals outputs/intelligence/calibration/historical_panel_labeled_sec_news_scored.parquet --out outputs/intelligence/calibration/historical_intelligence_panel_sec_news_scored.parquet`

`python -m scripts.walk_forward_intelligence_calibration --dataset outputs/intelligence/calibration/historical_intelligence_panel_sec_news_scored.parquet --target-col success_10d --return-cols next_5d_return next_10d_return --predictions-out outputs/intelligence/calibration/walk_forward_predictions_sec_news_scored.parquet --summary-out outputs/intelligence/calibration/walk_forward_summary_sec_news_scored.csv --train-days 252 --test-days 5 --step-days 5 --embargo-days 20 --min-train-rows 200`

## Notes

- Analyst recommendation rows are not rescored by default; their pressure score is already derived from buy/hold/sell counts.
- Sentiment is stored inside each row's `raw` payload as:
  - `model_sentiment_direction`
  - `model_sentiment_confidence`
  - `model_sentiment_score`
  - `model_sentiment_backend`
- The feature builder now prefers `raw.model_sentiment_score` when available.
