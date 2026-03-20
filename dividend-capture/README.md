# Dividend Capture Backtest

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

## Repository Structure

```text
dividend-capture/
├── src/
│   ├── original_universe/
│   │   ├── naive_dividend_capture/
│   │   │   ├── backtest.py
│   │   │   └── visualize.py
│   │   ├── regime_filtered/
│   │   │   ├── backtest.py
│   │   │   └── visualize.py
│   │   └── long_only_recovery/
│   │       ├── backtest.py
│   │       └── visualize.py
│   ├── pg_like_universe/
│   │   └── naive_dividend_capture/
│   │       ├── backtest.py
│   │       └── visualize.py
│   ├── utils/
│   └── README.md
├── data/
├── notes/
├── outputs/
│   ├── original_universe/
│   │   ├── naive_dividend_capture/
│   │   │   ├── results/
│   │   │   └── plots/
│   │   ├── regime_filtered/
│   │   │   ├── results/
│   │   │   └── plots/
│   │   ├── long_only_recovery/
│   │   │   ├── results/
│   │   │   └── plots/
│   │   └── README.md
│   ├── pg_like_universe/
│   │   ├── naive_dividend_capture/
│   │   │   ├── results/
│   │   │   └── plots/
│   │   ├── naive_dividend_capture_long_history/
│   │   │   ├── results/
│   │   │   └── plots/
│   │   └── README.md
│   └── scratch/
├── requirements.txt
└── README.md
```
## Typical Workflow

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run Naive Strategy (Original Universe)

```bash
python src/original_universe/naive_dividend_capture/backtest.py \
  --tickers KO PG JNJ XOM CVX T VZ PEP \
  --start 2018-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000 \
  --output-dir outputs/original_universe/naive_dividend_capture/results
```

### Run Naive Strategy (PG-like Universe)

```bash
python src/pg_like_universe/naive_dividend_capture/backtest.py \
  --tickers PG PEP KO CL KMB HSY WMT COST MCD \
  --start 2018-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000 \
  --output-dir outputs/pg_like_universe/naive_dividend_capture/results
```

### Run Long-History PG-like Experiment

```bash
python src/pg_like_universe/naive_dividend_capture/backtest.py \
  --tickers PG PEP KO CL KMB HSY WMT COST MCD \
  --start 1970-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000 \
  --output-dir outputs/pg_like_universe/naive_dividend_capture_long_history/results
```

### Run Long-Only Recovery Strategy

```bash
python src/original_universe/long_only_recovery/backtest.py \
  --outputs-dir outputs/original_universe/naive_dividend_capture/results \
  --train-end 2021-12-31 \
  --test-start 2022-01-01 \
  --trade-hold 1 \
  --regime-hold 1 \
  --rolling-window 8 \
  --overreaction-threshold 1.1 \
  --underreaction-threshold 0.9 \
  --min-avg-return 0.0 \
  --min-win-rate 0.50 \
  --output-dir outputs/original_universe/long_only_recovery/results
```

### Visualize Results

```bash
python src/original_universe/long_only_recovery/visualize.py \
  --input-file outputs/original_universe/long_only_recovery/results/long_only_recovery_test_trades.csv \
  --plot-dir outputs/original_universe/long_only_recovery/plots
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
