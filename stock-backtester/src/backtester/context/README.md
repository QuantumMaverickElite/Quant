# Market Context

Purpose
-------

Context features provide market/regime information that can adjust or filter
signals without replacing the underlying strategy.

Current implementation
----------------------

- `market_context.py` — packaged context structures and calculations.
- `scripts/run_market_context_features.py` — current batch entry point.

Connects to
-----------

Context consumes feature/price tables and produces `outputs/context/` artifacts;
mean-reversion and allocator research may consume those artifacts.

Tests
-----

Use the bounded context smoke scripts documented in `scripts/README.md`.

See also
--------

- [`docs/research_notes/COMBINED_SIGNAL_RESEARCH.md`](../../../docs/research_notes/COMBINED_SIGNAL_RESEARCH.md)
