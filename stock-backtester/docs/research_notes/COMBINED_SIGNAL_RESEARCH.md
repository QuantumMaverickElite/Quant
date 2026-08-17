# Combined Signal Research

Purpose
-------

This is the navigation point for research that tests a base mean-reversion
signal with context, volatility, correlation/deformation, or intelligence
adjustments. It is a map of existing workflows, not a claim that any run is the
official production baseline.

Research layers
---------------

1. **Baseline:** peer-spread/mean-reversion signals from
   `scripts/run_mean_reversion_signals.py` and `scripts/run_peer_spread_features.py`.
2. **Context:** `scripts/apply_context_to_mean_reversion_signals.py` consumes
   market-context artifacts.
3. **Correlation/deformation:** `scripts/run_regime_correlation_features.py`
   and `scripts/apply_deformation_weights_to_mean_reversion_signals.py` add
   optional peer/regime adjustments.
4. **Risk/volatility:** survivable-volatility and volatility/context scripts can
   filter or scale candidates; their exact combinations are experiment-specific.
5. **Intelligence:** `scripts/apply_intelligence_to_signals.py` and related
   historical/operational intelligence scripts are distinct from the current
   event-learning/LLM research line.
6. **Evaluation:** mean-reversion backtests, Monte Carlo scripts, allocator
   evaluations, and Rust stress exports compare the resulting layers.

Where to look
-------------

- Signal inputs/outputs: `outputs/signals/`
- Context outputs: `outputs/context/`
- Correlation outputs: `outputs/correlation/`
- Intelligence outputs: `outputs/intelligence/`
- Relevant implementation docs: `docs/large_universe_pipline.md`,
  `docs/research_notes/regime_correlation_deformation.md`, and
  `docs/market_intelligence_experiment_summary_2026_06_23.md`.

Authority and preservation
--------------------------

The packaged mean-reversion builder and documented output contracts are the
current structural authorities. Official combined baselines and preferred
ablations are **USER DECISION REQUIRED**; do not delete or normalize historical
runs until those are named.

Typical question
----------------

To test “ML with and without volatility/correlation,” begin with the baseline
signal command, identify the corresponding context/correlation artifacts, then
use the relevant evaluator. Record the exact inputs and output paths for any
comparison; this document does not execute the workflow.
