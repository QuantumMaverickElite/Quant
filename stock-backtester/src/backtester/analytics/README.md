# Analytics

Purpose
-------

Reusable volatility, GARCH-style, entropy, and state-feature calculations.

Current implementation
----------------------

- `volatility.py` and `fast_volatility.py` — volatility features.
- `entropy.py` — return and directional entropy.
- `volatility_state.py` — volatility state representation.

Connects to
-----------

Analytics consume price history and feed decision/context layers, MarketState,
allocator experiments, and large-universe context outputs.

Important commands
------------------

See `scripts/run_market_context_features.py` and the runbooks in `docs/systems/`.

Tests
-----

Several legacy `scripts/test_*.py` programs are smoke or data-dependent checks;
their classification is recorded in [`scripts/README.md`](../../../scripts/README.md).

See also
--------

- [`docs/systems/volatility_engines.md`](../../../docs/systems/volatility_engines.md)
- [`docs/systems/entropy_engine.md`](../../../docs/systems/entropy_engine.md)
