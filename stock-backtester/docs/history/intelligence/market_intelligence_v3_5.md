# Market Intelligence v3.5: Historical Panel Seed Builder

This patch creates the missing seed panel for walk-forward ML training.

## Why

`historical_intelligence_panel.parquet` does not exist automatically. It needs to be built from historical signal rows, then labeled, then joined to point-in-time historical features.

This patch adds:

- `src/backtester/intelligence/historical_panel_builder.py`
- `scripts/build_historical_intelligence_panel_seed.py`

## Anti-lookahead rule

Do not join the current `intelligence_features_opportunity_scored.csv` or `contextual_event_features.csv` onto old historical rows. Those files describe the current news/event snapshot, not historical point-in-time news.

For the first historical panel, use:

- historical signal rows
- forward return labels
- point-in-time SEC features

Historical news can be added later after we collect dated news/event features.

## Build sequence

1. Build a historical seed from real signal rows:

`python -m scripts.build_historical_intelligence_panel_seed --signals outputs/signals/mean_reversion_latest_with_intelligence.parquet --tickers-file data/intelligence/historical/sec_eval_tickers.txt --start 2025-01-01 --end 2026-05-28 --top-n-per-date 50 --exclude-latest-date --out outputs/intelligence/calibration/historical_panel_seed.parquet`

2. Label outcomes:

`python -m scripts.build_outcome_labels --signals outputs/intelligence/calibration/historical_panel_seed.parquet --out outputs/intelligence/calibration/historical_panel_labeled.parquet --download-prices --download-period 3y --horizons 5 10 20 --success-horizon 10`

3. Join point-in-time SEC features:

`python -m scripts.build_historical_sec_features --sec-sources data/intelligence/historical/raw/sec_eval_2025_2026.jsonl --signals outputs/intelligence/calibration/historical_panel_labeled.parquet --features-out outputs/intelligence/historical/sec_features_historical_panel.parquet --joined-out outputs/intelligence/calibration/historical_panel_labeled_sec.parquet --windows 1 7 30 90`

4. Build calibration dataset without current news/event CSVs:

`python -m scripts.build_intelligence_calibration_dataset --labeled-signals outputs/intelligence/calibration/historical_panel_labeled_sec.parquet --out outputs/intelligence/calibration/historical_intelligence_panel.parquet`

5. Run walk-forward:

`python -m scripts.walk_forward_intelligence_calibration --dataset outputs/intelligence/calibration/historical_intelligence_panel.parquet --target-col success_10d --return-cols next_5d_return next_10d_return --predictions-out outputs/intelligence/calibration/walk_forward_predictions.parquet --summary-out outputs/intelligence/calibration/walk_forward_summary.csv --train-days 252 --test-days 5 --step-days 5 --embargo-days 20 --min-train-rows 200`

## Notes

- `--tickers-file` keeps the first historical panel aligned to the tickers for which SEC data was fetched.
- `--exclude-latest-date` avoids mixing the current diagnostic slice into the historical train/test flow.
- If the seed is too small, lower `--top-n-per-date` only if runtime is the issue; otherwise expand the date range or ticker coverage.
