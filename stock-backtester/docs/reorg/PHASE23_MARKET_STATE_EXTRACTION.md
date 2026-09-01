# Phase 23: MarketState implementation extraction

Phase 23 characterized the MarketState family, added deterministic behavioral
contracts, and moved two script-local implementation clusters under `src/`.
It did not change state policy, thresholds, formulas, schemas, outputs, or
allocator authority.

## Family and ownership

| Role | Current owner / entry point | Status |
| --- | --- | --- |
| State schema, composition, posture | `src/backtester/decision/market_state.py` | Existing reusable package core |
| Fast-volatility feature construction | `src/backtester/decision/market_state_features.py` | Extracted reusable implementation |
| Feature-matrix command | `scripts/build_market_state_feature_matrix.py` | Stable download/output wrapper with helper re-exports |
| Historical GARCH portfolio mechanics | `src/backtester/backtests/market_state_portfolio.py` | Extracted reusable implementation |
| Portfolio command | `scripts/backtest_market_state_portfolio.py` | Stable orchestration/reporting wrapper with helper re-exports and `run_backtest` compatibility |
| Direct universe Monte Carlo | `scripts/monte_carlo_market_state.py` | Research; retains historical command-helper import |
| Scan, paper-trade, and smoke programs | `scripts/scan_market_state.py`, `test_market_state*.py`, `test_real_market_state.py` | Data-dependent research/compatibility; extraction deferred |
| Feature-matrix Monte Carlo and threshold variants | `research/threshold_rebalance/`, threshold commands in `scripts/` | Separate unresolved research lineage |

The fast feature builder uses `compute_fast_volatility_metrics`; the historical
portfolio path resolves GARCH metrics. They are not established as equivalent
and were not merged. Current code does not directly connect this family to the
large-universe mean-reversion context pipeline; shared volatility/entropy ideas
do not prove a runtime connection.

## Contracts and compatibility

`tests/test_market_state_contracts.py` protects exact MarketState fields and
composition, posture boundaries, rebalance selection, momentum windows and
clipping, entropy-row defaults, feature-row schema/as-of behavior, capped
weights without redistribution, lagged returns, summary schema, repeatability,
and script-helper identity with package owners.

Both command paths, arguments, defaults, path conventions, filenames, output
schemas, reporting, and download behavior remain in place. Numerical execution
requires the project environment; stdlib-only managed validation can still AST
parse all changed Python and reports the numerical contracts as dependency
skips.
