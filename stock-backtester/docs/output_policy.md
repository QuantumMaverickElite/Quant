# Outputs and artifact policy

`outputs/` is ignored generated research state, not source-code authority. Its
paths may nevertheless be filesystem APIs. Never infer that an artifact is
disposable, canonical, or reproducible merely because it is under `outputs/`.

The Phase 26 snapshot classifies every top-level family in the
[output taxonomy](reorg/PHASE26_OUTPUT_TAXONOMY.md) and
[machine-readable inventory](reorg/PHASE26_OUTPUT_INVENTORY.csv). Existing
writer/reader evidence is also recorded in
[OUTPUT_CONTRACTS.md](reorg/OUTPUT_CONTRACTS.md).

## Current categories

| Category | Typical location | Authority and treatment |
| --- | --- | --- |
| Pipeline contracts | `signals/`, `correlation/`, `context/`, `features/`, `feature_matrix/`, `allocator/`, `rust_inputs/`, `worker_ingest/` | Preserve paths and schemas until producer and every consumer migrate together |
| Durable research evidence | selected `experiments/`, `research/`, `backtests/`, threshold and intelligence runs | Preserve; baseline status requires explicit promotion and provenance |
| Training/model artifacts | `intelligence/training_runs/` | Preserve selected important runs; historical ML-policy is not current event-learning authority |
| Stress/Monte Carlo | `rust_stress/`, `monte_carlo/`, threshold run families | Summaries may be durable; paths/trials may be regenerable only with recorded seed and inputs |
| Reports and visualizations | `reports/`, comparisons, market-fabric frames | Regenerate where possible; preserve historically significant summaries selectively |
| Cache | `cache/` and `/tmp/quant_*` | Acceleration state, never research authority; retain while a downstream contract or exact reproduction needs it |
| Scratch/temp | `tmp/`, smoke/debug/retry workspaces | Temporary and non-authoritative, but delete only after checking tracked references and unique evidence |

The physical tree contains overlapping generations. Path alone is insufficient
to decide retention.

## Filesystem contracts

The large-universe chain uses explicit handoffs among matrices, peer/correlation
outputs, signals, context, Python portfolio inputs, Rust inputs, and stress
results. Intelligence uses staged worker, event, outcome, impact, LLM,
calibration, and training artifacts. Moving one stage requires migrating its
writer, readers, CLI defaults, documentation, and tests together.

The `/tmp/quant_*` families are not arbitrary scratch names. Commands use them
as explicit local handoffs for universes, price matrices, return matrices, peer
maps, and Rust inputs. Record exact paths and metadata even though `/tmp` is
ephemeral.

Do not merge or normalize output generations whose methods are not established
as equivalent. This includes package/tabular, staged cached, and one-pass
peer/spread outputs; threshold generations; MarketState generations; H20/H100;
current event-learning, operational intelligence fallback, and historical
ML-policy research.

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
- retention/promotion status and concise notes.

Do not require elaborate metadata for trivial local diagnostics. Do require it
before calling an artifact a durable baseline, using it as an official
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

### Cache

- Regenerable acceleration state; never baseline or research authority.
- Retain while recomputation cost or a downstream contract justifies it.
- Delete only after identifying the writer, regeneration command, consumers,
  and replacement inputs.

### Scratch

- Temporary and non-authoritative.
- Use run-specific names and short retention.
- Do not allow scratch paths to become implicit comparison baselines.
- Confirm there is no unique evidence or tracked reader before deletion.

### Pipeline intermediate

- Retain while downstream execution or exact reproduction depends on it.
- Treat path, schema, ticker/date order, dtype, and metadata as contracts.
- Move only producer and all consumers together.

### Durable baseline

- Preserve with manifest, input identity, code revision, command/config,
  schema, and explicit promotion status.
- Supersede explicitly; do not infer replacement from recency or filename.

### Research evidence

- Preserve meaningful results until a documented decision supersedes them.
- Prefer compact summaries plus the minimum artifacts needed to audit claims.
- Keep distinct methodologies and universes distinct.

### Training/model artifacts

- Preserve promoted models, manifests, selected predictions, evaluation/gate
  evidence, and important failure evidence.
- Do not retain every accidental trial forever; prune only after promotion and
  replacement decisions are documented.

### Stress and Monte Carlo

- Preserve configuration, seed, summary statistics, and selected diagnostics.
- Large trial/path tables may be pruned only when compact summaries and exact
  reproduction inputs are proven sufficient.

### Reports

- Regenerate routine plots and tables where inputs are stable.
- Preserve historically significant scorecards and conclusions selectively.
- A report is not methodology authority merely because it is human-readable.

## Safety and storage

- Do not commit large generated CSV, Parquet, PNG, binary, model, or frame
  artifacts to the source repository by default.
- Prefer compact summaries and compressed columnar formats for new heavy runs.
- Use hashes selectively for promoted baselines, migration-sensitive files,
  and anything about to be moved or removed.
- Do not delete `signals/`, correlation/context handoffs, worker-derived tables,
  Rust contracts, or intelligence evidence without run-level provenance and
  replacement authority.
- Generated does not mean disposable; old does not mean historical authority.

See [reproducibility.md](reproducibility.md) for broader experiment discipline
and [artifact_policy.md](artifact_policy.md) for external-storage guidance.
The older [output cleanup plan](output_cleanup_plan.md) is a historical proposal,
not current deletion authorization.
