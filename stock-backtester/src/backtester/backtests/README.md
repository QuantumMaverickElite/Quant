# Volatility Strategy Backtest

This module contains a research prototype of a volatility-based options trading strategy.

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
