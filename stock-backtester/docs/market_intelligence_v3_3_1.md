# Market Intelligence v3.3.1: Derived Calibration Targets

This patch fixes calibration rebuilds after adding SEC features.

## Problem

The previous workflow manually added `success_10d` to one calibration dataset. When rebuilding a new dataset from the SEC-joined signal table, that manual target was absent, so calibration failed with:

`ValueError: Target column not found: success_10d`

## Fix

`build_calibration_dataset` now derives binary target columns from forward return labels:

- `next_5d_return` -> `success_5d`
- `next_10d_return` -> `success_10d`
- `next_20d_return` -> `success_20d`

Missing forward returns stay missing, so the model does not train on unobservable outcomes.

## Next commands

Rebuild:

`python -m scripts.build_intelligence_calibration_dataset --labeled-signals outputs/signals/mean_reversion_allocator_intelligence_with_sec_smoke.parquet --intelligence-features outputs/intelligence/intelligence_features_opportunity_scored.csv --event-features outputs/intelligence/contextual_event_features.csv --out outputs/intelligence/calibration/intelligence_calibration_dataset_with_sec_smoke.parquet`

Recalibrate:

`python -m scripts.calibrate_intelligence_weights --dataset outputs/intelligence/calibration/intelligence_calibration_dataset_with_sec_smoke.parquet --target-col success_10d --model-type logistic --alpha 10.0 --out outputs/intelligence/calibration/intelligence_weight_calibration_10d_logistic_with_sec_smoke.json`
