# Market Intelligence v3.4: Walk-Forward ML Calibration

This patch adds walk-forward calibration for the intelligence/ML layer.

## Why

The ML model should not be trained and evaluated on the same historical slice. Random row splits are invalid here because rows share:

- market dates
- tickers
- overlapping forward-return labels
- sector/macro regimes
- repeated news and SEC context

This patch trains only on earlier dates, leaves an embargo gap, then predicts later dates.

## Files

- `src/backtester/intelligence/walk_forward_calibrator.py`
- `scripts/walk_forward_intelligence_calibration.py`

## Guardrails

- Training rows must be earlier than the prediction window.
- An embargo gap is applied between train and test windows.
- Feature medians, means, and standard deviations are fit on training rows only.
- The model writes out-of-sample predictions only.
- Ranking summaries are computed from those out-of-sample predictions.

## Example

For a real historical panel:

`python -m scripts.walk_forward_intelligence_calibration --dataset outputs/intelligence/calibration/historical_intelligence_panel.parquet --target-col success_10d --return-cols next_5d_return next_10d_return --predictions-out outputs/intelligence/calibration/walk_forward_predictions.parquet --summary-out outputs/intelligence/calibration/walk_forward_summary.csv --train-days 252 --test-days 5 --step-days 5 --embargo-days 20 --min-train-rows 200`

## Current limitation

The current evaluated dataset has only 73 rows from one signal date, so it is not enough for walk-forward ML. This patch is for the next stage: building a multi-date historical training panel.

## Historical news rule

Historical news can be used only as point-in-time data:

- article/source timestamp must be known
- feature timestamp must be <= signal decision timestamp
- labels must use returns after the decision timestamp
- full article text scraped today from old URLs should be treated carefully because it can include revised-page and survivorship bias

SEC filings are currently cleaner than GDELT for ticker-specific historical features. GDELT should remain a broad macro/sector discovery source unless we build stronger relevance and source-snapshot controls.
