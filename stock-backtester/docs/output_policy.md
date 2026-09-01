# Outputs and artifact policy

`outputs/` is ignored because commands generate its contents. Some files are
temporary, while others feed later pipeline stages or record important
experiments. Check who reads a path before moving or deleting it.

The Phase 26 snapshot classifies every top-level family in the
[output taxonomy](reorg/PHASE26_OUTPUT_TAXONOMY.md) and
[machine-readable inventory](reorg/PHASE26_OUTPUT_INVENTORY.csv). Existing
writer/reader evidence is also recorded in
[OUTPUT_CONTRACTS.md](reorg/OUTPUT_CONTRACTS.md).

## Current categories

| Category | Typical location | How to handle it |
| --- | --- | --- |
| Pipeline inputs and outputs | `signals/`, `correlation/`, `context/`, `features/`, `feature_matrix/`, `allocator/`, `rust_inputs/`, `worker_ingest/` | Several scripts read these paths directly; update producers and consumers together |
| Research results worth keeping | selected `experiments/`, `research/`, `backtests/`, threshold and intelligence runs | Keep results that support a decision, along with enough provenance to reproduce or audit them |
| Training/model artifacts | `intelligence/training_runs/` | Keep selected important runs; ML-policy runs belong to older research, not the current event-learning work |
| Stress/Monte Carlo | `rust_stress/`, `monte_carlo/`, threshold run families | Summaries may be durable; paths/trials may be regenerable only with recorded seed and inputs |
| Reports and visualizations | `reports/`, comparisons, market-fabric frames | Regenerate where possible; preserve historically significant summaries selectively |
| Cache | `cache/` and `/tmp/quant_*` | Regenerable acceleration data; keep it while downstream work or exact reproduction depends on it |
| Scratch/temp | `tmp/`, smoke/debug/retry workspaces | Usually disposable, but first check for readers and one-off results that were never copied elsewhere |

Older and newer runs often share a directory. A filename alone is not enough to
decide what should be kept.

## Filesystem contracts

The large-universe chain uses explicit handoffs among matrices, peer/correlation
outputs, signals, context, Python portfolio inputs, Rust inputs, and stress
results. Intelligence uses staged worker, event, outcome, impact, LLM,
calibration, and training artifacts. If you move one of these paths, update its
writer, readers, CLI defaults, documentation, and tests at the same time.

The `/tmp/quant_*` families are not arbitrary scratch names. Commands use them
as explicit local handoffs for universes, price matrices, return matrices, peer
maps, and Rust inputs. Record exact paths and metadata even though `/tmp` is
ephemeral.

Keep results from different methods separate unless the research shows they are
equivalent. This applies to the three peer/spread implementations, threshold
and MarketState variants, H20/H100 runs, event learning, the operational
intelligence fallback, and older ML-policy experiments.

## Metadata for new significant runs

A meaningful backtest, training run, stress run, baseline comparison, or
research result should write a small `manifest.json` (or equivalent structured
metadata) beside its outputs. Record, where applicable:

- `experiment_name` and registry/config identifier;
- `experiment_id`, `run_id`, and UTC timestamp;
- Git revision and dirty-tree status;
- exact command and material parameters;
- typed config or a stable config reference;
- random seed and sampling procedure;
- universe and date range;
- input artifact paths, sizes, and important hashes;
- output paths, formats, schemas, and schema versions;
- model/provider/version identifiers;
- dependency or environment fingerprint when material;
- retention status, baseline status, and concise notes.

Do not require elaborate metadata for trivial local diagnostics. Do require it
before calling an artifact a baseline, using it as an official
comparison input, or retaining a large run indefinitely. Avoid absolute
machine-specific paths when a repository-relative or declared external path is
sufficient.

## Placement for new runs

Prefer shallow predictable locations:

```text
outputs/experiments/<experiment_name>/<run_id>/
outputs/intelligence/training_runs/<run_id>/
outputs/cache/<contract-family>/
```

Stable pipeline products remain in their existing semantic contract folders.
A run directory should normally contain a manifest, compact summary, and only
the heavy artifacts explicitly requested. Do not create a new top-level folder
for every experiment.

## Retention policy

### Caches

- Caches speed up work but do not define a research result.
- Retain while recomputation cost or a downstream contract justifies it.
- Delete only after identifying the writer, regeneration command, consumers,
  and replacement inputs.

### Temporary files

- Treat these as temporary.
- Use run-specific names and short retention.
- Do not let an undocumented scratch file become a comparison baseline.
- Confirm there is no unique evidence or tracked reader before deletion.

### Files passed between pipeline stages

- Retain while downstream execution or exact reproduction depends on it.
- Treat path, schema, ticker/date order, dtype, and metadata as contracts.
- Move only producer and all consumers together.

### Baselines

- Keep the manifest, input identity, code revision, command/config,
  schema, and explicit promotion status.
- Supersede explicitly; do not infer replacement from recency or filename.

### Research results

- Keep meaningful results until a documented decision supersedes them.
- Prefer compact summaries plus the minimum artifacts needed to audit claims.
- Keep distinct methodologies and universes distinct.

### Training runs and models

- Keep selected models, manifests, predictions, evaluation/gate
  evidence, and important failure evidence.
- Do not retain every accidental trial forever; prune only after promotion and
  replacement decisions are documented.

### Stress tests and Monte Carlo runs

- Keep the configuration, seed, summary statistics, and selected diagnostics.
- Large trial/path tables may be pruned only when compact summaries and exact
  reproduction inputs are proven sufficient.

### Reports and plots

- Regenerate routine plots and tables where inputs are stable.
- Keep scorecards and conclusions that matter to the research history.
- A polished report does not make its underlying method the project default.

## Safety and storage

- Do not commit large generated CSV, Parquet, PNG, binary, model, or frame
  artifacts to the source repository by default.
- Prefer compact summaries and compressed columnar formats for new heavy runs.
- Use hashes selectively for selected baselines, migration-sensitive files,
  and anything about to be moved or removed.
- Do not delete `signals/`, correlation/context handoffs, worker-derived tables,
  Rust contracts, or intelligence evidence without run-level provenance and
  documented replacement.
- Generated files are not automatically disposable, and old files are not
  automatically important.

See [reproducibility.md](reproducibility.md) for broader experiment discipline
and [artifact_policy.md](artifact_policy.md) for external-storage guidance.
The older [output cleanup plan](output_cleanup_plan.md) is a historical proposal,
not current deletion authorization.
