# Phase 21: staged peer/spread implementation extraction

Phase 21 moves reusable staged cached-matrix computation out of command scripts
without changing quantitative methodology.

## Ownership

- `src/backtester/correlation/peer_search.py` owns staged peer selection.
- `src/backtester/correlation/peer_spreads.py` owns staged peer-basket spread
  computation and candidate filtering.
- `scripts/large_universe_peer_search.py` and
  `scripts/generate_peer_basket_spreads.py` remain stable command wrappers and
  compatibility exports.

The other two regimes remain separate: package/tabular behavior is owned by
`src/backtester/correlation/spreads.py`, while the one-pass cached implementation
remains in `scripts/run_peer_spread_features_from_cached_matrix.py` for a later
phase. No regime is promoted as research authority by this extraction.

The staged schema remains historical, including `ticker_return` and
`avg_peer_corr`. It is not normalized to the one-pass `stock_return` and
`top_k_avg_corr` names.

Phase 20 contracts now target the package functions and retain compatibility
checks for direct script-helper imports. No quantitative behavior was intended
to change.

Dependency-complete validation also exposed and repaired a pre-existing stale
`backtester.correlation` initializer export; no peer/spread behavior was
involved.
