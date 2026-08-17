# Sacred Workflows and Compatibility Contracts

## Explicitly sacred

These are the only commands currently listed in `configs/sacred_scripts.json`:

```text
python scripts/run_mean_reversion_signals.py --help
python scripts/run_market_intelligence_live.py --help
python scripts/export_rust_matrix_inputs.py --help
python scripts/threshold_rebalance_fast_v3.py --help
```

The manifest currently checks command availability/help parsing, not full behavioral equivalence or golden outputs. Do not silently expand the sacred list during Phase 0.

## High-risk / likely compatibility contracts

These paths are not formally sacred yet, but moving them requires wrappers and contract tests:

- `scripts/build_universe.py` through `scripts/generate_peer_basket_spreads.py` large-universe chain.
- `scripts/export_rust_matrix_inputs.py`, `export_rust_portfolio_inputs.py`, and `export_rust_stress_inputs.py`.
- `rust_engine/src/` interfaces for binary prices, metadata JSON, orders CSV, direction values, and output summaries.
- `scripts/workers/*.sh`, including SSH dispatch, remote bundle contents, redaction, `PYTHONPATH=src`, and CWD assumptions.
- `scripts/run_worker_sources_to_events.sh` and local `worker_ingest/` conventions.
- `outputs/signals/`, `outputs/context/`, `outputs/correlation/`, and `outputs/intelligence/` path families.
- `outputs/rust_inputs/`, `outputs/rust_stress/`, and market-fabric frame/overlay paths.
- `/tmp/quant_universes`, `/tmp/quant_returns`, `/tmp/quant_rust_matrix`, and related documented temporary paths.
- `PYTHONPATH=src` invocations and scripts that insert `src` into `sys.path`.

## Compatibility policy

The existing reorganization policy is retained: move implementation behind a stable interface first, leave a wrapper at the old command path, compare outputs, and deprecate only after explicit validation.

## User decision required

Confirm which remote worker conventions and output runs must become formally sacred rather than merely high-risk.
