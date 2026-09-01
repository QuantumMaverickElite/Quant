# Research

Put experiment-specific code, comparisons, ablations, and diagnostics here.
If code becomes useful across experiments, move the reusable part into `src/`.

- Reusable implementation belongs in `src/`.
- Stable user-facing commands belong in `scripts/`.
- Validation belongs in `tests/`.
- Repository maintenance belongs in `tools/`.

Current research families:

- [`combined_signals/`](combined_signals/) — allocator and signal comparisons.
- [`event_learning/`](event_learning/) — event-dataset audits and LLM benchmarks.
- [`mean_reversion/`](mean_reversion/) — mean-reversion evaluation, robustness,
  and same-universe controls.
- [`correlation/`](correlation/) — deformation evaluation and correlation
  diagnostics.
- [`dividend_capture/`](dividend_capture/) — four older dividend-event research
  variants kept separately; none is the current production strategy.
- [`threshold_rebalance/`](threshold_rebalance/) — threshold/rebalance
  comparisons and feature-matrix Monte Carlo research.
