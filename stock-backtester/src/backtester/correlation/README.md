# Correlation and Deformation

Purpose
-------

Correlation modules build regime-aware peer relationships and deformation
features used by large-universe research.

Current implementation
----------------------

- `features.py`, `regime.py`, `spreads.py`, `tracker.py`, and `io.py` support
  the package/tabular correlation path.
- `peer_search.py` owns staged cached-matrix peer selection.
- `peer_spreads.py` owns staged cached-matrix peer-basket spread computation.
- `scripts/run_regime_correlation_features.py` is the main feature-generation
  entry point; `apply_deformation_weights_to_mean_reversion_signals.py` applies
  the optional adjustment.

The package/tabular, staged cached-matrix, and one-pass cached-matrix peer
flows are distinct computational regimes. The one-pass implementation remains
in `scripts/run_peer_spread_features_from_cached_matrix.py`; it is not an alias
for the staged modules.

The staged spread output intentionally retains `ticker_return` and
`avg_peer_corr`. The one-pass output retains `stock_return` and
`top_k_avg_corr`.

Research evaluation and diagnostics now live under
`research/correlation/`; they do not own this reusable implementation.

Connects to
-----------

Inputs are returns/price matrices and context features. Outputs are written to
`outputs/correlation/` and may feed peer-spread evaluation, allocator research,
and market-fabric visualization.

Tests
-----

`tests/test_peer_spread_contracts.py` protects peer selection, staged spread
arithmetic/schema, one-pass helpers, and the downstream schema distinction.

See also
--------

- [`docs/research_notes/regime_correlation_deformation.md`](../../../docs/research_notes/regime_correlation_deformation.md)
- [`docs/research_notes/COMBINED_SIGNAL_RESEARCH.md`](../../../docs/research_notes/COMBINED_SIGNAL_RESEARCH.md)
