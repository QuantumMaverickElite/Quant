# Current Architecture

This is a description of the repository as it exists on the Phase 0 branch. It is not a target architecture and does not imply that the newer research path has replaced older operational code.

## Core backtest flow

```text
price data
  -> strategy positions or event trades
  -> optional GARCH/regime routing
  -> position/event engine
  -> metrics and plots
  -> outputs/backtests or outputs/reports
```

Primary code is under `src/backtester/`; the command surface is mostly under `scripts/`.

## Mean-reversion and large-universe flow

```text
universe builder
  -> price matrix
  -> returns matrix
  -> correlated-peer search
  -> peer-basket spread features
  -> mean-reversion signals
  -> volatility/entropy market context
  -> optional correlation-deformation weighting
  -> Python portfolio evaluation or Rust stress testing
  -> scorecards and market-fabric visualization
```

The package correlation modules are reusable implementation. Large-universe orchestration remains script-heavy and uses binary matrix metadata, literal output paths, and `/tmp/quant_*` conventions.

Mean-reversion evaluation and controls are now separated under
`research/mean_reversion/`; `scripts/` retains the pipeline entry points that
build peer spreads, signals, context, and deformation artifacts.

## Intelligence flows

### Legacy / operational fallback

```text
provider documents
  -> source fetch/load
  -> heuristic claims/evidence graph
  -> price-risk features
  -> MarketIntelligenceEngine report
  -> optional signal confidence adjustment
```

This path is still exposed by `backtester.intelligence` and protected by the sacred workflow manifest. It is not safe to archive until operational use is decided.

### Current event-learning research

```text
worker/provider payloads
  -> normalized source rows
  -> event fact table
  -> time-safe forward outcome labels
  -> event-impact dataset
  -> optional API/mock LLM structured features
  -> event-day aggregation
  -> baseline or walk-forward learning
  -> future bounded allocator overlay
```

Evaluation and benchmark analysis is kept separate from pipeline commands in
`research/event_learning/evaluation/`. It audits event-impact artifacts,
constructs deterministic LLM benchmark samples, and compares classification
runs. The event-learning documentation explicitly requires
`event_time <= signal_time` and says LLM output must not directly control
allocation. This path is active research and is not yet promoted to allocator
authority.

The current implementation is physically grouped as:

- `src/backtester/intelligence/events/` — event facts, schemas, labels, impact
  datasets, event-day aggregation, and event features.
- `src/backtester/intelligence/llm/` — contextual extraction, semantic
  classification/clustering, LLM classification joins, and NLP runtime.
- `src/backtester/intelligence/features/` — historical news feature and
  sentiment transformations plus historical panel construction. This is a
  research transformation layer between source acquisition and learning;
  it is not the `events/` schema layer, the `llm/` runtime layer, or allocator
  authority.

Combined-signal comparison and allocator-ablation research is physically
grouped under `research/combined_signals/`; it consumes existing
allocator/intelligence artifacts and does not own reusable implementation.
- `src/backtester/intelligence/calibration/` — calibration dataset assembly,
  fitted intelligence weights, and time-safe walk-forward calibration. It
  consumes research feature tables and preserves the existing calibration
  artifact paths; it is not a promoted allocator authority.
- Historical training commands remain user-facing under `scripts/`; their
  shared manifest/step-launch mechanics live in
  `backtester.intelligence.training_orchestration`. Batch, pool, and long-run
  policy remain distinct and their baseline authority is unresolved.
- `src/backtester/intelligence/historical_feature_builder.py` remains at the
  root as the SEC-specific historical feature builder, separate from both
  `features/` and `calibration/` for now.

## Computational regimes

### Package-oriented Python

Used for reusable analytics, decisions, strategies, position/event engines, and smaller experiments.

### Matrix-oriented Python

Used for large-universe data preparation, peer search, matrix allocators, and feature-matrix Monte Carlo. It favors dense arrays and explicit metadata files.

### Rust acceleration

The Rust `stress_mc` binary consumes exported orders and price matrices for repeated stress, randomization, exclusion, and portfolio simulations. Its file formats are cross-language contracts.

## Visualization flow

```text
returns + signals + context
  -> cached market graph frames
  -> allocator/trade overlays
  -> interactive visualizer
```

The current fabric stress metric includes forward-return information for diagnosis. It must not be silently reused as an ex-ante trading feature.

## Current architectural conclusion

The repository is a research operating system with a stable reusable core, script-heavy orchestration, a large intelligence history, and multiple computational regimes. Phase 0 records these boundaries; it does not collapse them.
