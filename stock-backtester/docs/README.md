# Quant Research Documentation

This folder contains modular documentation for the stock backtester and allocator research framework.

The root `README.md` is the project front page. These documents are the deeper reference modules.

## Documentation map

### Current

- [Architecture](architecture.md)
- [Output policy](output_policy.md)
- [Artifact policy](artifact_policy.md)
- [Reproducibility](reproducibility.md)
- [Subsystem READMEs](../src/backtester/)
- [Reorganization status](reorg/REORG_STATUS.md)

### Research

- [Combined signal research](research_notes/COMBINED_SIGNAL_RESEARCH.md)
- [Allocator findings](research_notes/allocator_findings.md)
- [Known limitations](research_notes/known_limitations.md)
- [Experiment notes](experiments/)

### History

The many `market_intelligence_v*.md` files document version history and are not
the current authority map. Start with [CURRENT_ARCHITECTURE](reorg/CURRENT_ARCHITECTURE.md)
and the intelligence README instead. Reorganization evidence is indexed under
[docs/reorg](reorg/README.md).

## Core Docs

- [Architecture](architecture.md)
- [Output Policy](output_policy.md)
- [Artifact Policy](artifact_policy.md)
- [Reproducibility](reproducibility.md)

## Systems

- [MarketState System](systems/market_state.md)
- [Entropy Engine](systems/entropy_engine.md)
- [Volatility Engines](systems/volatility_engines.md)
- [Regime Strategy](systems/regime_strategy.md)
- [Dividend Capture](systems/dividend_capture.md)
- [Options Overlay](systems/options_overlay.md)
- [CPU/GPU Matrix Backend](systems/cpu_gpu_matrix_backend.md)

## Experiments

-[Feature Matrix Monte Carlo](experiments/feature_matrix_monte_carlo.md)

- [Threshold Rebalance Experiments](experiments/threshold_rebalance.md)
- [Matrix Allocator Engine](experiments/matrix_allocator_engine.md)
- [Rebalance Frequency Tests](experiments/rebalance_frequency_tests.md)
- [Benchmark Scripts](experiments/benchmark_scripts.md)

## Math Reference

- [Strategy Math and Signal Definitions](strategy_math.md)

## Research Notes

- [Allocator Findings](research_notes/allocator_findings.md)
- [Known Limitations](research_notes/known_limitations.md)
- [Next Steps](research_notes/next_steps.md)
