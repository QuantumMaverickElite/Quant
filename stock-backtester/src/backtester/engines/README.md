# Engines and Allocators

Purpose
-------

Execution and allocator engines evaluate signals, positions, portfolio weights,
and matrix batches. They are reusable infrastructure, not a single strategy.

Current implementation
----------------------

- `position_engine.py`, `event_engine.py`, and `options_overlay_engine.py`.
- `matrix_allocator_engine.py` and `matrix_batch_ops.py` for matrix research.
- `array_backend.py` contains the experimental CPU/GPU backend boundary.

Connects to
-----------

Engines consume strategy/signal and MarketState inputs and produce backtest
metrics, portfolio returns, and research artifacts under `outputs/`.

Tests
-----

Use the offline registry/table tests for infrastructure contracts; legacy engine
smokes remain classified in `scripts/README.md`.

See also
--------

- [`docs/experiments/matrix_allocator_engine.md`](../../../docs/experiments/matrix_allocator_engine.md)
- [`docs/experiments/threshold_rebalance.md`](../../../docs/experiments/threshold_rebalance.md)
