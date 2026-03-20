# Dividend Capture Backtest

A small event-driven research project testing a naive dividend capture strategy on U.S. dividend-paying stocks.

## Overview

This project explores a simple question:

Can an investor buy a stock before its ex-dividend date, hold through the dividend event, sell shortly afterward, and earn excess returns?

The initial motivation came from the idea that stocks might not always fall by the full dividend amount on the ex-dividend date. If the price drop were consistently smaller than the dividend, a repeatable edge might exist. This repository tests that idea with a basic backtest.

## Strategy Tested

For each dividend event:

* buy at the close of the trading day before the ex-dividend date
* hold through the ex-dividend date
* sell after a chosen number of trading days
* include the dividend cash flow in the trade PnL

The backtest was run on the following tickers:

* KO
* PG
* JNJ
* XOM
* CVX
* T
* VZ
* PEP

## Research Goal

This project is not meant to present a production-ready trading strategy.

The goal is to test whether a naive dividend capture approach shows any basic statistical edge, and whether post-dividend behavior varies across stocks or holding periods.

## Initial Findings

Across the tested sample, the naive strategy was generally unprofitable.

Main observations:

* average returns were negative across tested holding periods
* the average ex-dividend price drop was greater than the dividend itself in this sample
* behavior varied significantly across stocks
* some names showed short-term recovery patterns, while others continued to drift lower

This suggests that a naive "buy before ex-date and sell after" approach is not enough on its own. Any possible edge likely depends on stock-specific behavior, filtering, or a different event-driven framework.

## Example Results

Summary from the initial runs:

| Hold Days | Avg Return | Total Gross PnL |
| --------- | ---------- | --------------- |
| 0         | -0.0672%   | -$1,719.43      |
| 1         | -0.0382%   | -$976.67        |
| 3         | -0.1964%   | -$5,027.96      |
| 5         | -0.1341%   | -$3,433.72      |

Average drop ratio in the sample:

* mean: 1.0754
* median: 1.0514

A drop ratio above 1 means the stock price fell by more than the dividend amount on average in this test sample.

## Repository Structure

```text
dividend-capture/
├── src/
│   └── backtest.py
├── data/
│   ├── raw/
│   ├── processed/
│   └── universe/
├── outputs/
│   ├── hold-0.csv
│   ├── hold-1.csv
│   ├── hold-3.csv
│   └── hold-5.csv
├── notes/
├── .gitignore
└── README.md
```

## Typical Session

A typical workflow for testing the dividend capture strategy:

Activate environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run a backtest across multiple dividend-paying stocks:

```bash
python src/dividend_capture_backtest.py \
  --tickers KO PG JNJ XOM CVX T VZ PEP \
  --start 2018-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000 \
  --csv outputs/results_hold_1.csv
```

Test different holding periods:

```bash
--hold-days 0   # sell on ex-date
--hold-days 1   # sell next day
--hold-days 3
--hold-days 5
```

Compare results:

* Win rate
* Average return
* Total PnL
* Drop ratio vs dividend

Outputs are saved as CSV files for further analysis.

---

## Interpretation Workflow

1. Run multiple holding periods
2. Identify patterns across tickers
3. Compare dividend vs price drop behavior
4. Look for asymmetries (e.g., consistent overreaction)
5. Evaluate whether edge exists on:

   * long side (capture)
   * short side (fade)

---

This project is intended for experimentation and hypothesis testing, not production trading.
