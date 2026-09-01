# Market Intelligence v3.4.1: Walk-Forward Confidence Column Fallback

This patch fixes walk-forward calibration on historical signal panels.

## Problem

The evaluated allocator files use:

- `allocator_confidence_pre_intelligence`
- `allocator_confidence_intelligence_adjusted`

The historical signal panel uses:

- `adjusted_confidence_pre_intelligence`
- `adjusted_confidence_intelligence_adjusted`

The walk-forward runner previously expected only the allocator column names.

## Fix

The runner now auto-detects either naming convention and exposes CLI overrides:

- `--baseline-confidence-col`
- `--heuristic-confidence-col`

## Retry command

`python -m scripts.walk_forward_intelligence_calibration --dataset outputs/intelligence/calibration/historical_intelligence_panel.parquet --target-col success_10d --return-cols next_5d_return next_10d_return --predictions-out outputs/intelligence/calibration/walk_forward_predictions.parquet --summary-out outputs/intelligence/calibration/walk_forward_summary.csv --train-days 252 --test-days 5 --step-days 5 --embargo-days 20 --min-train-rows 200`

If you want explicit columns:

`python -m scripts.walk_forward_intelligence_calibration --dataset outputs/intelligence/calibration/historical_intelligence_panel.parquet --target-col success_10d --return-cols next_5d_return next_10d_return --predictions-out outputs/intelligence/calibration/walk_forward_predictions.parquet --summary-out outputs/intelligence/calibration/walk_forward_summary.csv --train-days 252 --test-days 5 --step-days 5 --embargo-days 20 --min-train-rows 200 --baseline-confidence-col adjusted_confidence_pre_intelligence --heuristic-confidence-col adjusted_confidence_intelligence_adjusted`
