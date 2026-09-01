# MarketState system

The MarketState system combines volatility and entropy into an allocator-facing
object. It remains a research decision layer, not promoted allocator authority.

The core formula is:

```text
combined_multiplier = risk_multiplier * signal_trust_multiplier
```

Where:

```text
risk_multiplier          comes from volatility regime logic
signal_trust_multiplier  comes from entropy regime logic
combined_multiplier      scales the raw strategy score
```

## Purpose

MarketState lets the allocator react to market conditions without hardcoding every rule directly into the trading strategy.

It can control:

```text
allow_new_equity_positions
allow_options
capital_posture
preferred_strategy
```

## Capital Postures

Common postures include:

```text
NORMAL
CAUTIOUS
DEFENSIVE
CAPITAL_PRESERVATION
RESTRICTED
```

## Research Interpretation

The current MarketState allocator behaves more like a defensive momentum allocator than a pure alpha maximizer.

In strong bull markets, equal-weight and buy-and-hold benchmarks can outperform because the allocator may hold too much cash or reduce exposure too aggressively.

In rougher or mixed regimes, the allocator can become more competitive because it reduces drawdowns and improves risk-adjusted behavior.

## Open Question

```text
How do we make the allocator press harder in risk-on regimes
while preserving defensive behavior in unstable regimes?
```

## Related Scripts

Reusable ownership and stable commands are:

- `src/backtester/decision/market_state.py` — state schema, composition, and
  capital posture;
- `src/backtester/decision/market_state_features.py` — fast-volatility feature
  rows, rebalance dates, entropy-row conversion, and momentum scores;
- `scripts/build_market_state_feature_matrix.py` — download/output wrapper for
  the fast feature path;
- `src/backtester/backtests/market_state_portfolio.py` — historical GARCH-path
  portfolio scoring, weighting, return, and summary mechanics;
- `scripts/backtest_market_state_portfolio.py` — download, reporting, plotting,
  and compatibility command;
- `research/threshold_rebalance/monte_carlo_from_feature_matrix.py` — feature
  matrix threshold-rebalance research.

The fast-volatility feature path and historical GARCH portfolio path are not
declared equivalent. `scripts/scan_market_state.py`,
`scripts/test_market_state_trades.py`, `scripts/test_market_state.py`, and
`scripts/test_real_market_state.py` remain data-dependent research/smoke
commands. `scripts/monte_carlo_market_state.py` retains its historical import
of the portfolio command's `run_backtest` compatibility entry point.

Deterministic package and compatibility contracts live in
`tests/test_market_state_contracts.py`. They do not download prices.
