# Large-universe mean-reversion runbook

This runbook describes the current command and artifact flow. It does not
declare H20 versus H100 authority or claim equivalence between peer/spread
implementations.

## Pipeline

```text
build universe
  -> export price matrix
  -> export returns matrix
  -> peer search / correlation
  -> peer-basket spreads
  -> mean-reversion signals
  -> market context
  -> context adjustment
  -> optional correlation/deformation adjustment
  -> Python portfolio evaluation or Rust stress
  -> reports and market-fabric diagnostics
```

## Stages and owners

| Stage | Stable command | Reusable owner / status |
| --- | --- | --- |
| Universe selection | `scripts/build_universe.py` | Command-owned research policy |
| Price/Rust matrix export | `scripts/export_rust_matrix_inputs.py` | Compatibility-sensitive matrix contract |
| Returns export | `scripts/export_returns_matrix.py` | Compatibility-sensitive matrix contract |
| Staged peer search | `scripts/large_universe_peer_search.py` | `backtester.correlation.peer_search` |
| Staged peer spreads | `scripts/generate_peer_basket_spreads.py` | `backtester.correlation.peer_spreads` |
| Package/tabular peer features | `scripts/run_peer_spread_features.py` | `backtester.correlation.spreads` |
| One-pass cached peer features | `scripts/run_peer_spread_features_from_cached_matrix.py` | Separate script implementation; extraction deferred |
| Mean-reversion signals | `scripts/run_mean_reversion_signals.py` | `backtester.signals.mean_reversion` |
| Market context | `scripts/run_market_context_features.py` | `backtester.context` |
| Context adjustment | `scripts/apply_context_to_mean_reversion_signals.py` | Stable command path |
| Deformation features/adjustment | `scripts/run_regime_correlation_features.py`, `apply_deformation_weights_to_mean_reversion_signals.py` | `backtester.correlation`; research evaluation under `research/correlation/` |
| Portfolio evaluation | `scripts/backtest_mean_reversion_daily_portfolio.py` | `backtester.backtests.mean_reversion_daily_portfolio` |
| Rust stress | export commands plus `rust_engine/` | Explicit cross-language schemas |

## Peer/spread regimes

The three peer/spread paths are not established as quantitatively equivalent:

- **Package/tabular** consumes tabular prices/features and emits canonical
  downstream columns.
- **Staged cached** creates a peer map and then staged spreads. Its historical
  schema includes `ticker_return` and `avg_peer_corr`.
- **One-pass cached** computes directly from a cached matrix. Its downstream
  schema includes `stock_return` and `top_k_avg_corr`.

Do not silently normalize schemas or make one cached path call the other merely
for architectural uniformity.

## Reproducibility paths

Common handoff families include:

```text
/tmp/quant_universes/
/tmp/quant_rust_matrix/
/tmp/quant_returns/
/tmp/quant_peers/
```

These are temporary local locations but stable reproducibility interfaces.
Record their exact metadata files, input hashes, universe construction flags,
return settings, peer window/filter settings, and downstream output paths.

Generated pipeline artifacts also appear under `outputs/correlation/`,
`outputs/signals/`, `outputs/context/`, `outputs/backtests/`, and Rust-input or
stress folders. Retention authority is documented in
[output_policy.md](output_policy.md).

## Research discipline

- Verify universe membership and actual exported order counts before trusting a
  full-market experiment.
- Treat matrix metadata, ticker/date alignment, dtype, and binary shape as
  contracts.
- Preserve missing-data, overlap, ranking, and schema behavior behind tests.
- Compare against appropriate baselines and same-universe controls.
- Record horizon choices without declaring H20 or H100 canonical.
- Keep evaluation/diagnostic programs in the corresponding `research/` lane.

## Python daily portfolio evaluator

The daily evaluator consumes context-adjusted mean-reversion signals, filters
and ranks them per signal date, enters long positions on the next trading day,
holds overlapping positions for the configured trading-day horizon, and emits
orders, closed trades, daily equity, and summary metrics. Reusable order,
position, portfolio, and summary mechanics live in
`src/backtester/backtests/mean_reversion_daily_portfolio.py`; the script retains
downloads, paths, Parquet/CSV writes, and terminal presentation.

This is not a benchmark-authority decision and does not change or unify the
separate threshold, matrix, one-pass peer/spread, or Rust simulation paths.

## Safe validation

The deterministic peer/spread contracts are:

```bash
PYTHONPATH=src python tests/test_peer_spread_contracts.py
PYTHONPATH=src python tests/test_mean_reversion_daily_portfolio_contracts.py
```

Validate registry metadata and the full offline suite with:

```bash
PYTHONPATH=src python -m backtester.experiments validate
PYTHONPATH=src python -m unittest discover -s tests
```

`--help` checks are appropriate for individual commands. Do not run downloads,
large matrices, Rust workloads, or output-producing pipelines as documentation
validation.

The detailed verified-v3 experiment record previously occupying the misspelled
runbook path is preserved as
[`history/large_universe_pipeline_v3.md`](history/large_universe_pipeline_v3.md).
