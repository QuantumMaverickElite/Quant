# Outputs and artifact policy

`outputs/` contains generated research state, not source-code authority. This
phase documents the tree but does not move, delete, or promote any artifact.

## Current categories

| Category | Typical location | Treatment |
| --- | --- | --- |
| Durable research evidence | `outputs/experiments/`, selected summaries and scorecards | Preserve only with manifest, inputs, parameters, and provenance |
| Reports and backtests | `outputs/reports/`, `outputs/backtests/`, comparison folders | Regenerable unless explicitly promoted |
| Signals and features | `outputs/signals/`, `outputs/features/`, `outputs/context/`, `outputs/correlation/` | Pipeline contracts; retention authority varies |
| Matrices and caches | `outputs/cache/`, `outputs/feature_matrix/` and `/tmp/quant_*` | Regenerable or reproducibility interfaces; often large |
| Intelligence results | `outputs/intelligence/` | Mixed event datasets, audits, classifications, calibration, and training evidence |
| Training runs | `outputs/intelligence/training_runs/` | Research evidence; preserve manifests and promoted summaries |
| Monte Carlo and Rust stress | `outputs/monte_carlo/`, Rust-output locations | Usually regenerable; compact summaries preferred |
| Visual artifacts | market-fabric/frame/plot directories | Diagnostic unless explicitly promoted |
| Temporary run state | smoke, debug, retry, and timestamped scratch folders | No implied retention authority |

The physical taxonomy is inconsistent and contains overlapping generations.
Path alone is insufficient to decide whether an artifact is durable, a cache,
or disposable.

## Reproducibility interfaces

The `/tmp/quant_*` families are not arbitrary scratch names. Commands use them
as explicit handoff locations for universes, price matrices, return matrices,
peer maps, and Rust inputs. They are locally temporary but operationally
meaningful interfaces. Record exact paths and metadata in experiment manifests.

A durable experiment should record at least:

- Git commit and dependency versions;
- command and parameters;
- seed and sampled universe;
- input paths and hashes;
- output paths and schema/version;
- creation time and promotion/retention status.

See [reproducibility.md](reproducibility.md) and
[OUTPUT_CONTRACTS.md](reorg/OUTPUT_CONTRACTS.md).

## Save and retention principles

- Prefer compact summaries and Parquet/Zstd-compatible formats.
- Do not commit large matrices, per-trial curves, frame sets, or debug outputs.
- Do not delete `outputs/signals/` or intelligence evidence until manifests
  establish provenance and replacement authority.
- Cache only when recomputation cost justifies disk pressure.
- An artifact becomes a baseline only through an explicit research decision,
  not because it is old, large, or referenced by a script.

The older [artifact policy](artifact_policy.md) adds external-storage guidance.
The [output cleanup plan](output_cleanup_plan.md) is a historical/proposed
campaign, not authorization to delete anything.

## Future output cleanup

A future output campaign should:

1. inventory physical artifacts without following ignored overlays;
2. classify durable evidence, pipeline contracts, caches, and disposable runs;
3. choose official baselines and required manifests;
4. repair producers to emit predictable compact layouts;
5. archive or remove only after user approval and recoverability checks.

Until those prerequisites exist, output cleanup remains a documented proposal.
