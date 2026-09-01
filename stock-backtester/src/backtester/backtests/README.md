# Research backtests

## Mean-reversion daily portfolio

`mean_reversion_daily_portfolio.py` owns the reusable mechanics for the
large-universe Python daily evaluator: signal filtering and per-date ranking,
next-trading-day entries, configured trading-day exits, overlapping long
positions, confidence-weighted exposure, fees, mark-to-market equity, closed
trades, drawdown, and summary statistics.

`scripts/backtest_mean_reversion_daily_portfolio.py` retains signal-file and
price-download orchestration, output paths and formats, terminal reporting, and
compatibility re-exports. This evaluator remains separate from threshold,
matrix-allocator, and Rust stress methodologies. Its deterministic contracts
live in `tests/test_mean_reversion_daily_portfolio_contracts.py`.

## MarketState portfolio mechanics

`market_state_portfolio.py` owns reusable mechanics extracted from
`scripts/backtest_market_state_portfolio.py`: historical GARCH metric
resolution, date-local state construction, momentum scoring, capped weighting,
one-day-lag portfolio returns, drawdown, and summary statistics. The script
retains data download, CLI, progress, plotting, output writing, and its
historical `run_backtest` compatibility entry point.

This path is distinct from the fast-volatility feature-matrix implementation in
`backtester.decision.market_state_features`. Neither is promoted as allocator
authority. Offline behavior is protected by
`tests/test_market_state_contracts.py`.

## Volatility strategy prototype

`volatility_backtest.py` contains a research prototype of a volatility-based
options trading strategy.

---

## What this does

This backtest evaluates a strategy that trades volatility using:

- realized volatility (fast window)
- implied volatility proxy (slow window)
- volatility regime detection
- straddle / strangle style signals

---

## Core Idea

The strategy looks for a **volatility edge**:

vol_edge = realized_vol - implied_vol_proxy

If realized volatility is significantly higher than expected, the model assumes options are underpriced and enters a trade.

---

## Signal Types

- STRADDLE → strong volatility edge
- STRANGLE → moderate volatility edge
- NO_TRADE → no clear opportunity

---

## Trade Simulation

Each trade is modeled using:

- fixed holding period
- path-based returns (movement each day)
- theta-style decay
- capped downside (premium loss)

This is a simplified approximation of real options behavior.

---

## Example Results

The strategy behaves differently across assets:

- TSLA → strong performance (high volatility asset)
- NVDA → moderate performance
- AAPL → underperformance (low volatility asset)

---

## Key Insight

This strategy is **not universal**.

It performs best on:

- high-volatility stocks
- assets with large price swings

It performs poorly on:

- stable, low-volatility stocks

---

## Limitations

- Implied volatility is approximated (not real IV data)
- Options pricing is simulated (no Black-Scholes yet)
- No spreads, slippage, or liquidity modeling
- No portfolio-level risk management

This is a **research prototype**, not a production system.

---

## Usage

Run a backtest:

```bash
PYTHONPATH=src python src/backtester/backtests/volatility_backtest.py TSLA
```

---

## Next Steps

- Integrate real implied volatility data
- Add Black-Scholes pricing
- Improve PnL realism
- Build universe selection / strategy routing
- Combine with other strategies
