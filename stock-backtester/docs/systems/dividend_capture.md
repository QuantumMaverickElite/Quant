# Dividend Capture Strategy

The dividend capture strategy is an event-driven baseline that trades around ex-dividend dates.

## Basic Command

```bash
python -m backtester.cli \
  --strategy dividend \
  --tickers PG KO JNJ XOM CVX \
  --start 2018-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000
```

## What It Tracks

The dividend engine tracks:

```text
entry date
ex-dividend date
exit date
dividend income
price return
total return
trade-level PnL
```

## Research Role

This strategy is currently a naive baseline.

It is useful for event-driven testing, but it is not yet a finished dividend allocator.

Future improvements could include:

```text
tax-aware treatment
liquidity filters
slippage
sector filters
yield quality screens
earnings proximity
risk controls around dividend traps
```
