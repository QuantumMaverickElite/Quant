# Threshold-rebalance research

This directory contains comparative and Monte Carlo studies of threshold-
rebalance behavior. It does not own the strategy command implementations.

## Research programs

- `compare_threshold_portfolios.py` — compares completed threshold summaries
  across portfolio sizes 5, 8, and 12.
- `compare_fast_v2_drift_thresholds.py` — compares completed Fast V2
  drift-threshold runs and their portfolio metrics.
- `monte_carlo_from_feature_matrix.py` — samples prepared feature matrices and
  compares strategy, equal-weight-rebalance, and buy-and-hold outcomes.

The programs preserve their existing repository-root-relative inputs and
outputs. Run them from the `stock-backtester/` root with `PYTHONPATH=src`.

The executable strategy lineage remains under `scripts/`:

- `threshold_rebalance_fast_v2.py`
- `threshold_rebalance_from_feature_matrix.py`
- `threshold_rebalance_fast_v3.py`
- `threshold_rebalance_matrix_engine.py`

Fast V2/V3 and feature-matrix authority remains unresolved; Fast V3 is a
protected command. Reusable matrix allocator mechanics live in
`src/backtester/engines/matrix_allocator_engine.py`.

`monte_carlo_from_feature_matrix.py` still contains substantial simulation and
reporting implementation. Extracting reusable mechanics is deferred until a
separate behavior-preserving contract pass.
