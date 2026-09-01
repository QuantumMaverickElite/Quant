# Phase 26 output inventory

This is the generated-output inventory from 2026-09-01. Phase 26 changed no
quantitative code, schema, baseline choice, or generated file. The
machine-readable family inventory is
[`PHASE26_OUTPUT_INVENTORY.csv`](PHASE26_OUTPUT_INVENTORY.csv).

## Snapshot and method

`stock-backtester/outputs/` contains 1,501,563,492 bytes in 3,405 files and
469 nested directories beneath 34 direct top-level directories. The separate
historical dividend lane contains 4,536,281 bytes in 60 files and 19 nested
directories. All are ignored generated/local state.

The inventory used file metadata, extensions, shallow directory names,
representative small text/CSV metadata, tracked default paths, documentation,
and writer/reader searches. Large Parquet, binary, model, image, and trial
files were not exhaustively read or hashed. Classification is at top-level
family granularity; a directory may contain secondary roles recorded in the
notes.

### Largest top-level families

| Path | Bytes | Approximate size |
| --- | ---: | ---: |
| `outputs/intelligence/` | 498,789,670 | 475.68 MiB |
| `outputs/signals/` | 309,966,330 | 295.61 MiB |
| `outputs/threshold_rebalance/` | 187,314,564 | 178.64 MiB |
| `outputs/correlation/` | 118,836,411 | 113.33 MiB |
| `outputs/rust_stress/` | 91,209,372 | 86.98 MiB |
| `outputs/cache/` | 89,188,535 | 85.06 MiB |
| `outputs/monte_carlo/` | 44,626,465 | 42.56 MiB |
| `outputs/regime/` | 32,301,938 | 30.81 MiB |
| `outputs/compact_artifacts/` | 21,590,303 | 20.59 MiB |
| `outputs/market_graph_fabric_frames/` | 20,205,841 | 19.27 MiB |
| `outputs/rust_inputs/` | 17,789,178 | 16.97 MiB |
| `outputs/feature_matrix/` | 14,291,028 | 13.63 MiB |
| `outputs/reports/` | 12,161,753 | 11.60 MiB |
| `outputs/worker_ingest/` | 11,342,717 | 10.82 MiB |
| `outputs/experiments/` | 11,125,263 | 10.61 MiB |
| `outputs/allocator/` | 9,100,239 | 8.68 MiB |
| `outputs/features/` | 2,145,858 | 2.05 MiB |
| `outputs/research/` | 2,049,920 | 1.95 MiB |
| `outputs/storage_audit/` | 1,636,189 | 1.56 MiB |
| `outputs/backtests/` | 1,484,942 | 1.42 MiB |

The remaining 14 top-level directories total 4,656,101 bytes.

## Classification result

The 34 stock-backtester families have one primary classification each:

| Primary classification | Families | Bytes |
| --- | ---: | ---: |
| `MODEL_OR_TRAINING_ARTIFACT` | 1 | 498,789,670 |
| `PIPELINE_INTERMEDIATE` | 9 | 473,027,726 |
| `DURABLE_RESEARCH_EVIDENCE` | 4 | 201,974,689 |
| `STRESS_OR_MONTE_CARLO_ARTIFACT` | 3 | 135,835,837 |
| `CACHE` | 1 | 89,188,535 |
| `HISTORICAL_RESULT` | 7 | 55,240,063 |
| `REPORT` | 7 | 35,962,975 |
| `EXTERNAL_OPERATIONAL_INTERFACE` | 1 | 11,342,717 |
| `SCRATCH_OR_TEMP` | 1 | 201,280 |

Eight families are classed regenerable, 24 partially regenerable, and two not
proven regenerable. Thirteen top-level stock-backtester families are explicit
filesystem contracts. Twenty-five contain files needed by a pipeline or worth
retaining for research. Retention does not make a result the preferred baseline.

Provenance is uneven: four families have good provenance, nine partial
provenance, and 21 weak provenance. A filename, timestamp, or retained output
does not by itself establish a baseline.

## Writer, reader, and filesystem-contract map

| Contract | Writers | Readers / consumers | Decision |
| --- | --- | --- | --- |
| Large-universe matrices | universe, matrix, returns, filter, and market-cap commands under `outputs/cache/` and `/tmp/quant_*` | cached peer search, market-cap adjustment, Rust export | Keep paths; binary plus metadata pairs are contracts |
| Correlation and peer spreads | package/tabular, staged cached, one-pass cached, and regime-correlation commands | mean-reversion signals, context/deformation, diagnostics | Keep paths and the three regimes separate |
| Signals | peer-spread, mean-reversion, context, deformation, survivable-volatility, market-cap, allocator, and intelligence commands | Python portfolio, Rust export, allocator, intelligence, reports, research | Keep paths; selected current files coexist with historical variants |
| Context and allocator tables | context/deformation and combined-state builders | adjusted signals, allocator export, market fabric, evaluations | Keep literal default paths |
| Rust inputs and stress | Python exporters followed by Rust execution | Rust engine, change diagnostics, human stress review | Keep cross-language schemas and directories; do not infer regenerability from format alone |
| Feature matrices | MarketState and survivable-volatility builders | threshold generations, Monte Carlo, benchmarks | Keep paths and per-run metadata |
| Worker-derived tables | Chromebook parsers | event fact and outcome builders, legacy heuristics | Keep because workers and local readers exchange files through these paths |
| Market fabric | overlay/frame builders and augmenters | visualization commands and human diagnostics | Keep run manifests and named visualization handoffs |
| Research reports | backtest, scorecard, comparison, threshold, regime, and Monte Carlo commands | humans and subsequent comparison commands | Keep; choosing one as a baseline requires explicit provenance |

`strategy_scorecard.py` reads reports from `outputs/regime/`,
`outputs/dividend/`, and caller-selected roots. Similar directory names do not
mean that the contents share a schema or baseline.

## Families with multiple variants

### Signals and correlation

Portfolio, Rust, allocator, intelligence, and evaluation commands read 52
Parquet files directly from `outputs/signals/`. Moving or renaming them requires
updating those readers. The inventory does not choose H20 or H100 as the
default baseline.

`outputs/correlation/` contains package-oriented, staged cached, one-pass
cached, and regime/deformation artifacts. The three peer/spread regimes remain
distinct. Staged historical names and one-pass canonical downstream names are
not normalized or merged.

### Threshold rebalance

`outputs/threshold_rebalance/` contains 19 named run families across Fast V2,
Fast V3, feature-matrix, matrix-engine, weekly-check, and paired-curve
experiments. These are research evidence with weak run-level provenance.
No generation is the chosen default, and no paired-curve tree was deleted
merely because an older cleanup proposal called it a candidate.

### Intelligence

The 498,789,670-byte intelligence family combines several kinds of work:

| Subfamily | Bytes | Files | Status |
| --- | ---: | ---: | --- |
| `training_runs/` | 468,305,214 | 1,464 | Older ML-policy and training results with partial manifests |
| current event facts, outcomes, impact/day-impact datasets, LLM joins, calibration, and audits | about 19.1 MiB | mixed | Current event-learning research pipeline contracts |
| `worker_results/` | 3,164,127 | 32 | External worker/provider result interface |
| timestamped JSON report batches and current summaries | under 1.1 MiB | mixed | Operational heuristic/fallback reports |
| allocator and strategy comparison tables | about 5.4 MiB | mixed | Research and evaluation results; they do not define allocator behavior |

Historical ML-policy output belongs to older experiments, not the current
event-learning work or allocator. Operational heuristic summaries remain
available for the fallback path. Current event-learning tables pass data
between several stages and therefore remain in place.

### Rust, stress, and MarketState

`rust_inputs/` contains CSV, binary, and JSON contracts; `rust_stress/`
contains stress results and large trial tables. Neither was rewritten, run, or
deleted. MarketState scan, GARCH portfolio, feature-matrix, Monte Carlo, and
trade-plan artifacts stay separate; their shared name does not establish
methodological equivalence.

### Historical dividend outputs

`~/projects/quant/dividend-capture/outputs/` has 60 files: 34 under the
original-universe lane, 26 under the PG-like lane, and an empty `scratch/`
directory. CSV results, plots, and written notes retain four
distinct historical research families. Provenance is weak and exact
regeneration from live yfinance history is not proven.

The migrated research README and commands deliberately document the root path,
while `stock-backtester/outputs/dividend/` is a separate historical/package
lane with different lineage. Moving into either `outputs/dividend/` or a new
name would create ambiguity without a compatibility benefit. Phase 26 therefore
chooses `KEEP_ROOT_COMPATIBILITY`; no file was moved or rewritten. Empty
`dividend-capture/data/` and `notes/` placeholders remain local and empty.

## Baselines and provenance

Current documentation names individual signal/context artifacts and selected
scorecards as useful pipeline inputs, but no repository-wide official baseline
manifest exists. The best-provenanced families are compact historical
intelligence artifacts, market-graph frame runs with manifests, and the two
audit families. Feature-matrix metadata and many intelligence training
manifests provide partial provenance. Signals, correlation, threshold, Rust
stress, regime, MarketState, and dividend history generally lack one or more
of command, Git revision, exact inputs, seed, schema version, or promotion
status.

The project has not chosen between H20/H100 or the threshold generations, and
it has not promoted one intelligence training run. Phase 26 does not turn
retained files into official baselines.

## Why no files were moved or deleted

No generated file was moved or deleted. The only directory classified scratch,
`outputs/tmp/`, contains a named market-cap candidate signal referenced by an
experiment record and is not proven disposable. `outputs/stress/` and the
dividend `scratch/` lane are empty, so removing them offers zero byte savings
and no meaningful navigation payoff. The 89,188,535-byte cache is costly but
contains matrix/metadata and universe/returns handoffs with tracked consumers.

Consequently:

- files moved: 0;
- bytes moved: 0;
- files deleted: 0;
- bytes deleted: 0;
- top-level directory count: unchanged at 34;
- dividend compatibility tree: unchanged at 60 files and 4,536,281 bytes.

Some retained files may eventually prove unnecessary; the available provenance
was not strong enough to remove them safely during Phase 26.

## Where new runs should go

The current shallow semantic families are preferable to a mass move. New
significant experiments should default to:

```text
outputs/experiments/<experiment_name>/<run_id>/
outputs/intelligence/training_runs/<run_id>/
outputs/cache/<contract-family>/
```

Stable pipeline products should remain in their existing semantic contract
folders. New run directories should carry a manifest described in
[`output_policy.md`](../output_policy.md). A future retention pass may remove
individual runs after a replacement baseline and its hashes are recorded. It
should not require another wholesale directory reorganization.

## Remaining large or untidy areas

| Residual area | Classification |
| --- | --- |
| `signals/`, `correlation/`, `context/`, `cache/`, `rust_inputs/`, `worker_ingest/` | Other programs read these paths directly |
| threshold generations, regime history, dividend history, selected reports | Research history worth retaining |
| intelligence training runs and Rust stress trials | Retention requires a run-by-run baseline decision |
| old plots, curve-heavy Monte Carlo, paired threshold curves | Probably low value, but no manifest proves that a replacement exists |
| recurring training, model, report, and cache growth | Apply the current retention policy to future runs |

No major family remains `UNKNOWN`; uncertainty is recorded at artifact/run
level through provenance and regenerability notes.

## Conclusion

The inventory makes the useful and path-sensitive output families discoverable.
Caches and temporary files are not baselines, and new significant runs have a
defined location and metadata format. The remaining untidy directories are
documented well enough that another physical output-reorganization pass is not
needed.
