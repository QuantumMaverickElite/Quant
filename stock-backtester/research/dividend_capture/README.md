# Dividend Capture Backtest

> **Ownership status:** this is standalone historical research, not current
> package or production authority. Four distinct experiment families are
> preserved without promotion or merger. Deterministic relocation contracts
> live in `tests/test_dividend_capture_contracts.py`. Generated historical
> state remains at `~/projects/quant/dividend-capture/outputs/` as an explicit
> historical compatibility contract. Phase 26 classified and retained it
> without promoting any research generation.

A research project testing dividend-related trading ideas around ex-dividend dates.

## Overview

This project started with a simple question:

Can an investor buy a stock before its ex-dividend date, hold through the dividend event, sell shortly afterward, and earn excess returns?

The initial motivation came from the idea that stocks might not always fall by the full dividend amount on the ex-dividend date. If the price drop were consistently smaller than the dividend, a repeatable edge might exist. This repository tests that idea through a series of backtests, refinements, and visualizations.

## Research Goal

This project is not meant to present a production-ready trading strategy.

The goal is to explore whether dividend-related event behavior contains any statistical edge, and whether that behavior varies across:

- different stocks
- holding periods
- stock “profiles” (e.g., defensive vs energy)

## Key Findings

### Original Universe (Mixed Stocks)

The naive dividend capture strategy was generally unprofitable:

- average returns were negative across holding periods
- price drops often exceeded the dividend (drop ratio > 1)
- behavior varied widely across tickers

This showed that a naive, one-size-fits-all approach does not work.

### Refined Universe (PG-like Stocks)

After focusing on more stable, defensive dividend stocks:

- results improved significantly
- win rates increased
- some tickers showed consistent post-dividend recovery

This suggests the effect is **not universal**, but may exist within specific classes of stocks.

### Behavioral Insight

The data suggests two broad post-dividend behaviors:

- fast recovery (bounce shortly after ex-date)
- slower recovery or continuation downward

This leads to strategy specialization rather than a single unified approach.

## Research families

```text
research/dividend_capture/src/
├── original_universe/
│   ├── naive_dividend_capture/  # baseline backtest and visualization
│   ├── regime_filtered/         # distinct long/short regime methodology
│   └── long_only_recovery/      # distinct recovery methodology
└── pg_like_universe/
    └── naive_dividend_capture/  # same naive method, different universe
```

These are historical research programs, not reusable package implementation.
The package dividend-event baseline under `src/backtester/strategies/` remains
a separate ownership context.

## Typical Workflow

Run these examples from `stock-backtester/`. Output paths intentionally target
the retained repository-root compatibility lane. It contains 60 historical
CSV/plot/note artifacts across the four research families; exact regeneration
from live yfinance history is not proven.

### Setup

```bash
pip install -r research/dividend_capture/requirements.txt
```

### Run Naive Strategy (Original Universe)

```bash
python research/dividend_capture/src/original_universe/naive_dividend_capture/backtest.py \
  --tickers KO PG JNJ XOM CVX T VZ PEP \
  --start 2018-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000 \
  --output-dir ../dividend-capture/outputs/original_universe/naive_dividend_capture/results
```

### Run Naive Strategy (PG-like Universe)

```bash
python research/dividend_capture/src/pg_like_universe/naive_dividend_capture/backtest.py \
  --tickers PG PEP KO CL KMB HSY WMT COST MCD \
  --start 2018-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000 \
  --output-dir ../dividend-capture/outputs/pg_like_universe/naive_dividend_capture/results
```

### Run Long-History PG-like Experiment

```bash
python research/dividend_capture/src/pg_like_universe/naive_dividend_capture/backtest.py \
  --tickers PG PEP KO CL KMB HSY WMT COST MCD \
  --start 1970-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000 \
  --output-dir ../dividend-capture/outputs/pg_like_universe/naive_dividend_capture_long_history/results
```

### Run Long-Only Recovery Strategy

```bash
python research/dividend_capture/src/original_universe/long_only_recovery/backtest.py \
  --outputs-dir ../dividend-capture/outputs/original_universe/naive_dividend_capture/results \
  --train-end 2021-12-31 \
  --test-start 2022-01-01 \
  --trade-hold 1 \
  --regime-hold 1 \
  --rolling-window 8 \
  --overreaction-threshold 1.1 \
  --underreaction-threshold 0.9 \
  --min-avg-return 0.0 \
  --min-win-rate 0.50 \
  --output-dir ../dividend-capture/outputs/original_universe/long_only_recovery/results
```

### Visualize Results

```bash
python research/dividend_capture/src/original_universe/long_only_recovery/visualize.py \
  --input-file ../dividend-capture/outputs/original_universe/long_only_recovery/results/long_only_recovery_test_trades.csv \
  --plot-dir ../dividend-capture/outputs/original_universe/long_only_recovery/plots
```
## Interpretation Workflow

1. Run multiple holding periods
2. Compare results across tickers
3. Analyze drop ratio vs dividend
4. Identify behavioral patterns
5. Segment stocks into strategy-specific groups
6. Test refined models

## Notes

This project is focused on exploration and hypothesis testing, not production trading.

The goal is to iteratively refine ideas, test assumptions, and uncover structure in market behavior around dividend events.
