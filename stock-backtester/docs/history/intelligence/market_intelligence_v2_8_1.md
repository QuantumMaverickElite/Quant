# Market Intelligence v2.8.1

Fixes calibration on sparse intelligence/event features.

Changes:

- Keeps rows with a valid target instead of requiring every feature to be present.
- Drops feature columns that are entirely missing.
- Median-imputes partially missing numeric feature columns.
- Reports dropped all-missing features and imputation values in the calibration JSON.

For the current evaluated slice, use `next_10d_return` with `--model-type ridge`.

Reason:

`signal_success` was built from the configured 20-day horizon, but the current data does not yet have valid `next_20d_return` labels.
