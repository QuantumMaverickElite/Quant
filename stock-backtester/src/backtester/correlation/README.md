# Correlation and Deformation

Purpose
-------

Correlation modules build regime-aware peer relationships and deformation
features used by large-universe research.

Current implementation
----------------------

- `features.py`, `regime.py`, `spreads.py`, `tracker.py`, and `io.py`.
- `scripts/run_regime_correlation_features.py` is the main feature-generation
  entry point; `apply_deformation_weights_to_mean_reversion_signals.py` applies
  the optional adjustment.

Connects to
-----------

Inputs are returns/price matrices and context features. Outputs are written to
`outputs/correlation/` and may feed peer-spread evaluation, allocator research,
and market-fabric visualization.

Tests
-----

No dedicated offline contract suite exists yet; preserve the output contracts
documented in `docs/reorg/OUTPUT_CONTRACTS.md`.

See also
--------

- [`docs/research_notes/regime_correlation_deformation.md`](../../../docs/research_notes/regime_correlation_deformation.md)
- [`docs/research_notes/COMBINED_SIGNAL_RESEARCH.md`](../../../docs/research_notes/COMBINED_SIGNAL_RESEARCH.md)
