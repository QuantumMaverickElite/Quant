# Scripts: commands and research tools

`scripts/` contains commands you run directly. Most reusable calculations live
under `src/backtester/`; some older commands remain here because other scripts
or documented workflows still call their existing paths. This page highlights
the commands most useful when returning to the project.

## Current commands and pipelines

| Command | Role | Status / subsystem |
| --- | --- | --- |
| `run_mean_reversion_signals.py` | build peer-spread signals | current / signals |
| `run_peer_spread_features.py` | build peer features | current / large-universe |
| `large_universe_peer_search.py` | staged cached-matrix peer search | wrapper over `backtester.correlation.peer_search` |
| `generate_peer_basket_spreads.py` | staged cached-matrix spread generation | wrapper over `backtester.correlation.peer_spreads` |
| `run_peer_spread_features_from_cached_matrix.py` | one-pass cached-matrix peer/spread features | separate implementation; extraction deferred |
| `build_universe.py` | select a research universe | current / large-universe |
| `run_market_context_features.py` | generate market context | current / context |
| `run_regime_correlation_features.py` | generate regime/correlation features | current / correlation |
| `apply_context_to_mean_reversion_signals.py` | context adjustment | research pipeline |
| `apply_deformation_weights_to_mean_reversion_signals.py` | deformation adjustment | research pipeline |
| `backtest_mean_reversion_daily_portfolio.py` | evaluate a signal portfolio | wrapper over `backtester.backtests.mean_reversion_daily_portfolio` |
| `export_rust_matrix_inputs.py` / `export_rust_stress_inputs.py` | prepare Rust contracts | compatibility-sensitive |
| `summarize_rust_stress_runs.py` | summarize Rust results | research evaluator |
| `run_market_intelligence_live.py` | operational intelligence loop | live/provider assumptions |
| `run_market_intelligence_batch.py` | intelligence batch research | research / intelligence |
| `build_market_state_feature_matrix.py` | build fast-volatility MarketState features | wrapper over `backtester.decision.market_state_features` plus download/output orchestration |
| `backtest_market_state_portfolio.py` | run historical GARCH MarketState portfolio research | command over `backtester.backtests.market_state_portfolio`; also preserves `run_backtest` compatibility |

Historical ML-policy commands remain at their old paths and are compatibility
wrappers over `src/backtester/intelligence/ml_policy/`:

- `apply_ml_policy_strength.py`
- `validate_ml_policy_candidate.py`
- `sweep_ml_policy_strength.py`
- `permutation_test_ml_policy.py`

They support older ML-policy experiments and are not part of the current
event-learning approach.

## By subsystem

- **Mean reversion / large universe:** `run_*mean_reversion*`, `run_peer_spread*`,
  `generate_peer_basket_spreads.py`, and their evaluators.
  The staged cached command paths remain stable wrappers while reusable peer
  search and spread computation live in `src/backtester/correlation/`. The
  package/tabular and one-pass cached paths remain separate regimes.
  Daily overlapping-position portfolio mechanics live in
  `src/backtester/backtests/mean_reversion_daily_portfolio.py`; the historical
  evaluator command path remains stable.
  Evaluation, inspection, Monte Carlo, and same-universe control programs now
  live in [`../research/mean_reversion/`](../research/mean_reversion/).
- **Correlation/deformation:** `run_regime_correlation_features.py`,
  `apply_deformation_*`, and deformation diagnostics.
- **Intelligence and training:** `run_market_intelligence_*`, `build_*intelligence*`,
  `run_*training*`, and `scripts/legacy/intelligence_heuristics/`.
  The four historical training commands retain their paths while sharing
  lightweight mechanics from `backtester.intelligence.training_orchestration`.
- **Combined-signal research:** allocator comparisons and diagnostics now live
  in [`../research/combined_signals/`](../research/combined_signals/), along
  with allocator-signal builders and Monte Carlo comparisons; this is research
  analysis rather than general-purpose commands.
- **Threshold-rebalance research:** comparisons and feature-matrix Monte Carlo
  now live in [`../research/threshold_rebalance/`](../research/threshold_rebalance/).
  The executable strategy lineage remains here: `threshold_rebalance_fast_v2.py`,
  `threshold_rebalance_from_feature_matrix.py`, `threshold_rebalance_fast_v3.py`,
  and `threshold_rebalance_matrix_engine.py`.
- **MarketState research:** state composition lives in
  `backtester.decision.market_state`; reusable fast feature construction and
  historical GARCH portfolio mechanics live in the package modules documented
  above. The fast and GARCH paths remain distinct research generations.
- **Event-learning evaluation:** dataset audits and LLM benchmark programs now
  live in [`../research/event_learning/evaluation/`](../research/event_learning/evaluation/).
  Commands that build event facts, labels, datasets, and classifier inputs
  remain here as pipeline entry points.
- **Rust and matrix acceleration:** `export_rust_*`, `run_*market_fabric*.sh`,
  and Rust stress summarizers.
- **Visualization:** `visuals/` and `build_market_fabric_*` helpers.
- **Workers:** `scripts/workers/`; packaging and SSH assumptions are documented in
  `docs/reorg/SACRED_WORKFLOWS.md`.
- **Maintenance/audit:** these are no longer script commands; use
  [`../tools/reorg/`](../tools/reorg/README.md) for `reorg_audit.py`,
  `reorg_sacred_smoke.py`, and related inventory helpers.

## Tests and maintenance

Offline validation tests now live in [`../tests/README.md`](../tests/README.md).
Repository-maintenance tools now live in
[`../tools/reorg/README.md`](../tools/reorg/README.md). Neither category belongs
in this research-command directory.

The remaining test-named programs are not interchangeable: several use
`yfinance` or real data, while others are synthetic smoke executables. Check
the header and arguments before running one. A `test_*.py` filename does not
guarantee a small offline regression test.

Current classification of the remaining files:

- **LIVE/DATA-DEPENDENT TEST:** `test_entropy_engine.py`,
  `test_market_state.py`, `test_market_state_trades.py`,
  `test_options_overlay.py`, `test_real_market_state.py`,
  `test_real_volatility_decision.py`, `test_regime_router.py`.
- **SMOKE TEST / SYNTHETIC EXECUTABLE:** `test_position_sizing.py`,
  `test_survivable_volatility.py`, `test_volatility_decision.py`.
- **UNCERTAIN / NEEDS SEPARATE REVIEW:** none of the remaining files was moved
  on filename alone; scripts with mixed data and smoke behavior stay here until
  their invocation contracts are documented.

## Full inventory and runbooks

- [Script inventory](../docs/reorg/SCRIPT_INVENTORY.md)
- [Current architecture](../docs/architecture.md)
- [Sacred workflows](../docs/reorg/SACRED_WORKFLOWS.md)
- [Combined signal research](../docs/research_notes/COMBINED_SIGNAL_RESEARCH.md)
