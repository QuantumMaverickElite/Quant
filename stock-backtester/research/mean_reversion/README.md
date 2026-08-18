# Mean-reversion research

This directory contains evaluation, inspection, robustness, and control
programs around the packaged mean-reversion signal system.

## General evaluation

- `evaluate_mean_reversion_signals.py` evaluates signal and forward-return
  behavior across horizons.
- `evaluate_mean_reversion_by_compression_bucket.py` compares outcomes by
  market-context compression buckets.
- `inspect_mean_reversion_signals.py` provides bounded artifact diagnostics;
  it is not an automated test.

## Robustness / Monte Carlo

- `backtest_mean_reversion_monte_carlo.py` evaluates portfolio paths from
  signal returns.
- `stress_mean_reversion_monte_carlo.py` compares the signal universe with
  randomized controls.

## Control / benchmark

- `benchmark_same_universe_buy_hold.py` supplies a same-universe,
  equal-weight buy-and-hold control. It is a benchmark, not mean-reversion
  logic.

Core signal construction remains authoritative in
`src/backtester/signals/`; stable pipeline commands remain in `scripts/`.
H20/H100 and signal-horizon defaults here describe individual experiments,
not repository-wide authority.
