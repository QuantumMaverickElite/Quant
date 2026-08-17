# Phase 9: Intelligence Calibration Topology

The user-performed Phase 9 move groups the calibration family under
`src/backtester/intelligence/calibration/`:

- `calibration_dataset.py` — labeled dataset assembly and feature selection
- `weight_calibrator.py` — fitted logistic/ridge weights and JSON artifacts
- `walk_forward_calibrator.py` — time-safe fitting, prediction, and summaries

These modules share `feature_columns()` and form one dataset-to-calibration
boundary. Existing parquet, prediction/summary, and calibration JSON output
paths and schemas are unchanged.

`historical_feature_builder.py` remains at the intelligence root because it is
an SEC-specific point-in-time feature builder, not a calibrator. Provider/source
and operational/evaluation families remain deferred due to higher compatibility
risk. Intelligence topology cleanup pauses after this repair; the next target
is a focused script-family forensic pass.
