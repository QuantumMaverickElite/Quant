# Regime Strategy

The regime strategy is one of the original strategy systems in the project.

It uses market regime information to adjust strategy behavior through momentum, streaks, crash detection, leverage behavior, and router logic.

## Basic Regime Backtest

```bash
python -m backtester.cli \
  --strategy regime \
  --ticker SPY \
  --start 2015-01-01 \
  --end 2024-12-31
```

## Regime Router

The regime router converts volatility state into routing decisions.

Example:

```bash
python -m backtester.cli \
  --strategy regime \
  --ticker NVDA \
  --start 2015-01-01 \
  --end 2024-12-31 \
  --use-regime-router
```

## Research Role

The regime strategy is useful for testing how state-aware strategy rules behave compared with simpler baselines.

It is also useful for testing overlays such as options logic and conditional routing.
