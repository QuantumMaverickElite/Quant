# Market Intelligence v3.3: Enable SEC Features in Calibration

This patch makes `sec_*` columns trainable calibration features.

## What changed

`src/backtester/intelligence/calibration_dataset.py` now includes columns with the `sec_` prefix in `feature_columns`.

## Why

v3.2 can build and join point-in-time SEC filing features, but the calibration selector previously only trained on:

- `intelligence_*`
- `event_*`
- selected explicit columns such as `regime_break_score`

Without this patch, SEC features could appear in the joined signal table while the ML calibrator silently ignored them.

## Next command

Rebuild the calibration dataset from the SEC-joined signal table:

`python -m scripts.build_intelligence_calibration_dataset --labeled-signals outputs/signals/mean_reversion_allocator_intelligence_with_sec_smoke.parquet --intelligence-features outputs/intelligence/intelligence_features_opportunity_scored.csv --event-features outputs/intelligence/contextual_event_features.csv --out outputs/intelligence/calibration/intelligence_calibration_dataset_with_sec_smoke.parquet`

Then recalibrate:

`python -m scripts.calibrate_intelligence_weights --dataset outputs/intelligence/calibration/intelligence_calibration_dataset_with_sec_smoke.parquet --target-col success_10d --model-type logistic --alpha 10.0 --out outputs/intelligence/calibration/intelligence_weight_calibration_10d_logistic_with_sec_smoke.json`

The current SEC smoke file only covers a few tickers, so this is a wiring test, not yet a real ML upgrade.
