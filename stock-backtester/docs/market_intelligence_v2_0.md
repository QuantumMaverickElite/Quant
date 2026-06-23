# Market Intelligence v2.0

v2.0 starts calibration.

## What it does

1. Builds forward outcome labels:
   - `next_5d_return`
   - `next_20d_return`
   - `max_drawdown_next_20d`
   - `signal_success`

2. Builds calibration examples by joining:
   - signal features
   - intelligence features
   - contextual event features
   - outcome labels

3. Fits a first-pass bounded calibration model:
   - logistic model for `signal_success`
   - ridge model for continuous outcomes

## Important limitation

This does not yet solve historical news availability. If current live intelligence features are joined onto old historical rows, that is not a valid historical backtest.

The correct long-term process is walk-forward:

```text
week t known features -> predict week t+1 weights -> reveal week t+1 outcomes -> update
```

## Example

```bash
python -m scripts.build_outcome_labels \
  --signals outputs/signals/mean_reversion_latest_with_intelligence.parquet \
  --download-prices \
  --out outputs/intelligence/calibration/outcome_labeled_signals.parquet
```

```bash
python -m scripts.build_intelligence_calibration_dataset \
  --labeled-signals outputs/intelligence/calibration/outcome_labeled_signals.parquet \
  --intelligence-features outputs/intelligence/intelligence_features.csv \
  --event-features outputs/intelligence/contextual_event_features.csv \
  --out outputs/intelligence/calibration/intelligence_training_examples.parquet
```

```bash
python -m scripts.calibrate_intelligence_weights \
  --dataset outputs/intelligence/calibration/intelligence_training_examples.parquet \
  --target-col signal_success
```
