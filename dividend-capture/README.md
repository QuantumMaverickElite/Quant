# Dividend Capture Backtest

A small research project testing dividend-related trading ideas around ex-dividend dates.

## Overview

This project started with a simple question:

Can an investor buy a stock before its ex-dividend date, hold through the dividend event, sell shortly afterward, and earn excess returns?

The initial motivation came from the idea that stocks might not always fall by the full dividend amount on the ex-dividend date. If the price drop were consistently smaller than the dividend, a repeatable edge might exist. This repository tests that idea through a series of backtests, visualizations, and refinements.

## Research Goal

This project is not meant to present a production-ready trading strategy.

The goal is to test whether dividend-related event behavior contains any basic statistical edge, and whether that behavior changes across stocks, holding periods, and stock types.

## Initial Findings

Across the original mixed-stock universe, the naive strategy was generally unprofitable.

Main observations:

- average returns were negative across tested holding periods
- the average ex-dividend price drop was greater than the dividend itself in that sample
- behavior varied significantly across stocks
- some names showed short-term recovery patterns, while others continued to drift lower

This suggested that a naive "buy before ex-date and sell after" approach was too broad and that any possible edge would need to come from stock-specific behavior or more targeted filtering.

## Refined Findings

After narrowing the universe to a set of more stable, defensive, dividend-paying stocks, results improved materially.

The strongest patterns appeared in a subset of PG-like names, where post-dividend behavior looked more favorable than in the original mixed universe. Those results suggested that the effect, if real, is not universal but may be concentrated in specific classes of stocks.

The later visualizations also suggested that these stocks may split into two broad behavioral groups:

- faster post-dividend bounce profiles
- slower recovery / continuation profiles

This project explores those patterns through iterative testing rather than assuming a single universal strategy.

## Example Results

Summary from the initial mixed-universe runs:

| Hold Days | Avg Return | Total Gross PnL |
| --------- | ---------- | --------------- |
| 0         | -0.0672%   | -$1,719.43      |
| 1         | -0.0382%   | -$976.67        |
| 3         | -0.1964%   | -$5,027.96      |
| 5         | -0.1341%   | -$3,433.72      |

Average drop ratio in the original sample:

- mean: 1.0754
- median: 1.0514

A drop ratio above 1 means the stock price fell by more than the dividend amount on average in that test sample.

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
│   │       └── backtest.py
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
│   │   ├── regime_filtered/
│   │   ├── long_only_recovery/
│   │   └── README.md
│   ├── pg_like_universe/
│   │   ├── naive_dividend_capture/
│   │   └── README.md
│   └── scratch/
└── README.md
```

## Typical Session

A typical workflow for the original mixed-universe naive strategy:

Activate environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install pandas yfinance matplotlib
```

Run the original mixed-universe naive backtest:

```bash
python src/original_universe/naive_dividend_capture/backtest.py \
  --tickers KO PG JNJ XOM CVX T VZ PEP \
  --start 2018-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000 \
  --csv outputs/original_universe/naive_dividend_capture/results/hold_1.csv
```

Run the PG-like universe backtest:

```bash
python src/pg_like_universe/naive_dividend_capture/backtest.py \
  --tickers PG PEP KO CL KMB HSY WMT COST MCD \
  --start 2018-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000 \
  --csv outputs/pg_like_universe/naive_dividend_capture/results/hold_1.csv
```

Generate visualizations for the original universe:

```bash
python src/original_universe/naive_dividend_capture/visualize.py \
  --outputs-dir outputs/original_universe/naive_dividend_capture/results \
  --plot-dir outputs/original_universe/naive_dividend_capture/plots
```

Generate visualizations for the PG-like universe:

```bash
python src/pg_like_universe/naive_dividend_capture/visualize.py \
  --outputs-dir outputs/pg_like_universe/naive_dividend_capture/results \
  --plot-dir outputs/pg_like_universe/naive_dividend_capture/plots
```

## Interpretation Workflow

1. Run multiple holding periods  
2. Identify patterns across tickers  
3. Compare dividend vs price-drop behavior  
4. Use visualizations to separate stock-specific behaviors  
5. Refine the universe or model based on observed structure  

## Current Direction

The current direction of the project is not to treat dividend capture as a universal strategy.

Instead, the project is moving toward a more selective framework:

- identify stock groups with favorable post-dividend behavior  
- separate faster bounce profiles from slower recovery profiles  
- test narrower universes rather than broad mixed baskets  
- continue validating ideas out of sample  

This project is intended for experimentation and hypothesis testing, not production trading.
