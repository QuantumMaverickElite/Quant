# Current architecture

Stock Backtester is a research operating system with reusable Python
implementation, stable command paths, research-specific programs, deterministic
contracts, generated artifacts, and a Rust acceleration boundary. This document
describes current ownership; it does not promote unresolved research variants.

## Repository layers

| Path | Responsibility |
| --- | --- |
| `src/backtester/` | Reusable implementation and typed domain interfaces |
| `scripts/` | Stable commands, compatibility wrappers, and remaining command-heavy programs |
| `research/` | Experiments, ablations, controls, evaluations, and diagnostics |
| `tests/` | Small deterministic offline contract and regression tests |
| `tools/` | Repository maintenance rather than quantitative research |
| `configs/` | Audit, storage, workflow, and registry policy |
| `outputs/` | Ignored generated artifacts and filesystem contracts; not source authority |
| `rust_engine/` | Rust stress and repeated-computation implementation |
| `docs/` | Current reference documentation plus clearly indexed history |

The intended boundary is: reusable quantitative behavior belongs under
`src/`; commands orchestrate it; research programs answer questions; tests
protect stable behavior.

## Core computational paths

### Position and event backtests

```text
price or event data
  -> strategy positions or event trades
  -> optional volatility/regime decisions
  -> position or event engine
  -> metrics and reports
```

Analytics, decisions, strategies, and engines live in their corresponding
`src/backtester/` packages. Some older end-to-end orchestration remains in
scripts and is future extraction debt.

### Large-universe mean reversion

```text
universe
  -> price matrix
  -> returns matrix
  -> peer search / correlation
  -> peer-basket spreads
  -> mean-reversion signals
  -> market context
  -> optional context/deformation adjustment
  -> Python portfolio evaluation or Rust stress
  -> reporting and market-fabric diagnostics
```

The detailed command and artifact sequence is documented in the
[large-universe runbook](large_universe_pipeline.md).

The daily overlapping-position evaluator is owned by
`backtester.backtests.mean_reversion_daily_portfolio`; its stable download,
file-output, and reporting command remains
`scripts/backtest_mean_reversion_daily_portfolio.py`. This evaluator is a
Python research path and is not declared equivalent to the matrix allocator,
threshold-rebalance implementations, or Rust stress engine.

Peer/spread computation has three intentionally distinct regimes:

1. **Package/tabular:** `src/backtester/correlation/spreads.py`, invoked by
   `scripts/run_peer_spread_features.py`.
2. **Staged cached matrix:** `peer_search.py` and `peer_spreads.py`, invoked
   by `large_universe_peer_search.py` and
   `generate_peer_basket_spreads.py`.
3. **One-pass cached matrix:**
   `scripts/run_peer_spread_features_from_cached_matrix.py`; implementation
   extraction is deferred.

These regimes are not established as equivalent. The staged schema retains
`ticker_return` and `avg_peer_corr`; the one-pass schema retains
`stock_return` and `top_k_avg_corr`. H20 versus H100 authority is unresolved.

### Market state, allocators, and threshold research

Volatility and entropy analytics feed decision and MarketState layers, which
can influence allocator scores and permissions. Reusable mechanics live under
`src/backtester/analytics/`, `decision/`, `context/`, and `engines/`.
`backtester.decision.market_state` owns the allocator-facing state object and
composition policy. Fast-volatility feature-matrix mechanics live in
`backtester.decision.market_state_features`; the historical GARCH portfolio
simulation mechanics live separately in
`backtester.backtests.market_state_portfolio`. Their stable commands remain
`scripts/build_market_state_feature_matrix.py` and
`scripts/backtest_market_state_portfolio.py`.

Those fast-volatility and GARCH paths are separate research generations, not
established equivalents. Scan, paper-trade, smoke, and Monte Carlo commands
retain their historical behavior and authority remains research-only or
unresolved; MarketState is not promoted allocator authority by this ownership
split.
Threshold-rebalance commands remain under `scripts/`; comparisons and
Monte Carlo studies live under `research/threshold_rebalance/`. Fast V2,
feature-matrix, Fast V3, and matrix-engine authority remains unresolved.

## Intelligence architecture

Three intelligence lineages coexist and must not be collapsed:

### Current event-learning research

```text
provider or worker payloads
  -> normalized event facts
  -> time-safe forward outcomes
  -> event-impact datasets
  -> optional structured LLM classification
  -> event-day aggregation
  -> baseline or walk-forward learning
  -> bounded future allocator research
```

Implementation is grouped under:

- `src/backtester/intelligence/events/` — schemas, facts, labels, datasets,
  aggregation, and event features;
- `src/backtester/intelligence/llm/` — extraction, classification, semantic
  processing, joins, and NLP runtime;
- `src/backtester/intelligence/features/` — historical news/sentiment feature
  transformations;
- `src/backtester/intelligence/calibration/` — calibration datasets and
  time-safe weight fitting.

Evaluation lives in `research/event_learning/evaluation/`. Event-learning is
the current research direction, not promoted allocator authority.

### Operational heuristic fallback

`MarketIntelligenceEngine`, provider/source loading, evidence graphs, price
risk, reporting, and signal integration remain wired and protected. They are a
legacy operational fallback, not the event-learning research architecture.
Provider and ingestion modules remain near the intelligence package root
because worker and path contracts constrain movement.

### Historical ML-policy research

Reusable historical ML-policy helpers live under
`src/backtester/intelligence/ml_policy/`; historical command paths remain
wrappers under `scripts/`. This research line is neither current
event-learning authority nor allocator authority. Its versioned documentation
is under `docs/history/intelligence/`.

Training commands remain under `scripts/`; shared launch/manifest mechanics
live in `backtester.intelligence.training_orchestration`. Batch, pool, and
long-run training policy remains unresolved.

## Experiment and configuration registry

`src/backtester/experiments.py` provides metadata-only discovery of registered
components, pipelines, commands, experiments, typed parameters, and
configurations. It does not execute experiments or decide research authority.

Use:

```bash
PYTHONPATH=src python -m backtester.experiments list
PYTHONPATH=src python -m backtester.experiments describe <id>
PYTHONPATH=src python -m backtester.experiments config <id>
PYTHONPATH=src python -m backtester.experiments validate
```

## Python and Rust boundary

Python owns data preparation, feature/signal construction, orchestration, and
reporting. Rust consumes explicit exported matrix/order contracts for repeated
stress, exclusion, randomization, and portfolio simulation. Rust formats are
cross-language contracts; neither implementation should silently reinterpret
the other's schemas.

## Workers and root-level lanes

The repository-root `worker_ingest/` directory is an ignored local cache and
synchronization interface. Two tracked parsers consume its exact
`~/projects/quant/worker_ingest/chromebook` path, while current worker commands
use a distinct remote `~/quant-worker` contract and copy newer results into
`outputs/intelligence/worker_results/`. It is operational infrastructure, not a
peer research project, and its path is intentionally retained.

The 66 former ignored intelligence overlays are preserved under the tracked,
human-readable repository-root `archive/intelligence_overlays/` tree. Their old
source directories are intentionally absent and archive verification is
source-independent after migration.

Standalone historical dividend research now lives under
[`research/dividend_capture/`](../research/dividend_capture/README.md), distinct
from the package event-strategy baseline. Deterministic contracts protect its
path-independent behavior; no generation is promoted as authority. The root
`dividend-capture/` directory retains ignored historical outputs plus empty
local `data/` and `notes/` placeholders as a documented compatibility lane.
Phase 26 retained it because exact regeneration is unproven and
`stock-backtester/outputs/dividend/` has different lineage. See the
[Phase 25B record](reorg/PHASE25B_ROOT_PHYSICAL_CLEANUP.md) and current
[output taxonomy](reorg/PHASE26_OUTPUT_TAXONOMY.md).

## Output ownership

Generated artifacts are not source authority, but major output paths are often
interfaces between commands, research stages, Python, Rust, and worker-derived
tables. The current 34-family inventory, writer/reader map, preservation
decisions, and provenance findings live in the
[Phase 26 output taxonomy](reorg/PHASE26_OUTPUT_TAXONOMY.md). Retention and the
metadata standard for new significant runs live in
[output_policy.md](output_policy.md). H20/H100, threshold-generation, and
intelligence-training authority remain unresolved.

## Current, fallback, historical, unresolved

| Status | Meaning |
| --- | --- |
| Current implementation | Actively owned reusable code or stable command path |
| Current research | Active research direction without production promotion |
| Operational fallback | Still wired/protected, but not the preferred research architecture |
| Historical research | Preserved tooling or evidence; not current authority |
| Unresolved | Multiple variants remain and no authority choice has been made |

Known unresolved areas include H20/H100 baselines, threshold V2/V3 lineage,
training modes and official durable output baselines.
