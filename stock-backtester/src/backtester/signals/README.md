# Signals

Purpose
-------

Signal builders turn feature tables into strategy-facing signals. The packaged
mean-reversion implementation is the current authority for peer-spread signals.

Current implementation
----------------------

- `mean_reversion.py` — peer search, spread construction, and signal logic.
- `../intelligence/` — optional intelligence adjustments are separate from the
  base signal builder.

Connects to
-----------

Inputs are price/return and peer-feature tables. Scripts in `scripts/` write
signal artifacts under `outputs/signals/`, which context and deformation layers
may consume.

Important commands
------------------

- `scripts/run_mean_reversion_signals.py`
- `scripts/run_peer_spread_features.py`
- `research/mean_reversion/evaluate_mean_reversion_signals.py`

Tests
-----

No dedicated signal-only offline test currently exists. Use the documented
large-universe and evaluation scripts only with bounded fixtures.

See also
--------

- [`docs/large_universe_pipeline.md`](../../../docs/large_universe_pipeline.md)
- [`docs/research_notes/COMBINED_SIGNAL_RESEARCH.md`](../../../docs/research_notes/COMBINED_SIGNAL_RESEARCH.md)
