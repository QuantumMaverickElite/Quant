# System architecture

Stock Backtester is a quantitative research codebase with reusable Python
implementation, stable command paths, research-specific programs, deterministic
contracts, generated artifacts, and a Rust acceleration boundary. The sections
below show where those pieces live and how the main workflows connect. They do
not choose between research variants that are still being compared.

## Where things live

| Path | Responsibility |
| --- | --- |
| `src/backtester/` | Reusable implementation and shared domain types |
| `scripts/` | Commands you run directly, plus compatibility wrappers and command-heavy workflows |
| `research/` | Experiment-specific code, ablations, controls, evaluations, and diagnostics |
| `tests/` | Small deterministic offline contract and regression tests |
| `tools/` | Maintenance scripts for auditing or reorganizing the repository; not part of the research pipeline |
| `configs/` | Audit, storage, workflow, and registry policy |
| `outputs/` | Ignored files produced by commands; several subpaths feed later pipeline stages |
| `rust_engine/` | Rust stress and repeated-computation implementation |
| `docs/` | Current reference documentation plus clearly indexed history |

Reusable quantitative code belongs under `src/`. Commands orchestrate it,
research programs answer specific questions, and tests protect stable behavior.

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
`src/backtester/` packages. A few older end-to-end workflows remain in scripts
because they are tightly coupled to their commands.

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

These regimes have not been shown to be equivalent. The staged schema retains
`ticker_return` and `avg_peer_corr`; the one-pass schema retains
`stock_return` and `top_k_avg_corr`. The project has not chosen H20 or H100 as
the default baseline.

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

The fast-volatility and GARCH paths come from separate lines of research and
have not been shown to be equivalent. Scan, paper-trade, smoke, and Monte Carlo
commands keep their existing behavior; moving reusable code did not make any
of them the default allocator.
Threshold-rebalance commands remain under `scripts/`; comparisons and
Monte Carlo studies live under `research/threshold_rebalance/`. The project has
not selected Fast V2, feature-matrix, Fast V3, or the matrix engine as the
preferred implementation.

## Intelligence research

Three intelligence approaches remain in the repository:

### Current event-learning research

```text
provider or worker payloads
  -> normalized event facts
  -> time-safe forward outcomes
  -> event-impact datasets
  -> optional structured LLM classification
  -> event-day aggregation
  -> baseline or walk-forward learning
  -> controlled allocator experiments
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

Evaluation lives in `research/event_learning/evaluation/`. Event learning is
the current research direction, but it does not yet control allocation.

### Operational heuristic fallback

`MarketIntelligenceEngine`, provider/source loading, evidence graphs, price
risk, reporting, and signal integration remain available as an operational
fallback. They are separate from the event-learning work.
Provider and ingestion modules remain near the intelligence package root
because worker and path contracts constrain movement.

### Historical ML-policy research

Reusable historical ML-policy helpers live under
`src/backtester/intelligence/ml_policy/`; historical command paths remain
wrappers under `scripts/`. This code is kept for older experiments; it is not
the current event-learning approach and does not control allocation. Versioned
notes live under `docs/history/intelligence/`.

Training commands remain under `scripts/`; shared launch/manifest mechanics
live in `backtester.intelligence.training_orchestration`. Batch, pool, and
long-run training policy remains unresolved.

## Experiment and configuration registry

`src/backtester/experiments.py` lists registered components, pipelines,
commands, experiments, typed parameters, and configurations. It does not run
experiments or choose which result becomes the baseline.

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

The 66 old intelligence overlays are stored under the tracked repository-root
`archive/intelligence_overlays/` tree. Their former ignored directories have
been removed, and the archive verifier no longer needs them.

Standalone historical dividend research now lives under
[`research/dividend_capture/`](../research/dividend_capture/README.md), distinct
from the package event-strategy baseline. Deterministic contracts protect its
path-independent behavior; none is treated as the current production strategy.
The root `dividend-capture/` directory retains ignored historical outputs plus
empty local `data/` and `notes/` placeholders because older experiments use
that location.
Phase 26 retained it because exact regeneration is unproven and
`stock-backtester/outputs/dividend/` has different lineage. See the
[Phase 25B record](reorg/PHASE25B_ROOT_PHYSICAL_CLEANUP.md) and current
[output taxonomy](reorg/PHASE26_OUTPUT_TAXONOMY.md).

## How outputs connect the pipeline

Commands often pass data through files: Python writes Rust inputs, signal
builders feed portfolio tests, and worker parsers feed event-learning jobs.
Moving one of these paths requires updating its readers too. The
[output policy](output_policy.md) explains retention and metadata for new runs;
the [Phase 26 inventory](reorg/PHASE26_OUTPUT_TAXONOMY.md) maps all 34 output
families. The project has not chosen preferred H20/H100, threshold, or
intelligence-training runs.

## Status labels used in the docs

| Status | Meaning |
| --- | --- |
| Current implementation | Reusable code or a command used by current workflows |
| Current research | Active research direction without production promotion |
| Operational fallback | Still wired/protected, but not the preferred research architecture |
| Historical research | Older code or results kept so past work can be inspected or repeated |
| Unresolved | Multiple variants remain and the project has not chosen one |

Open research decisions include H20/H100 baselines, threshold V2/V3, training
modes, and which output runs should be kept as long-term baselines.
