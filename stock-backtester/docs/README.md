# Documentation authority map

This directory separates current operating documentation from historical
research and migration evidence. Start here instead of reconstructing the
system from versioned notes or reorganization phases.

## Current authoritative surface

| Topic | Authority |
| --- | --- |
| Repository navigation and quick start | [Project README](../README.md) |
| Current architecture and ownership | [Architecture](architecture.md) |
| Large-universe pipeline | [Large-universe runbook](large_universe_pipeline.md) |
| Research lifecycle and benchmark discipline | [Research workflow](research_workflow.md) |
| Generated outputs and artifacts | [Output policy](output_policy.md) |
| Reproducibility principles | [Reproducibility](reproducibility.md) |
| Intelligence implementation and authority | [Intelligence README](../src/backtester/intelligence/README.md) |
| Event-learning research | [Event-learning README](../research/event_learning/README.md) |
| Experiment/config registry | [Experiment registry](reorg/EXPERIMENT_REGISTRY.md) and [parameter registry](reorg/PARAMETER_CONFIG_REGISTRY.md) |
| Offline tests | [Tests README](../tests/README.md) |

Subsystem-local READMEs under `src/backtester/`, `research/`, `scripts/`,
`configs/`, and `rust_engine/` provide the next level of detail.

## Current reference areas

- [System guides](systems/) — market state, entropy, volatility, regimes,
  options, dividend-capture context, and matrix backends.
- [Strategy math](strategy_math.md) — mathematical definitions and formulas.
- [Intelligence storage policy](intelligence/storage_policy.md).
- [Output contracts](reorg/OUTPUT_CONTRACTS.md) and
  [sacred workflows](reorg/SACRED_WORKFLOWS.md).

Some detailed experiment and research-note documents remain useful evidence but
are not general operating instructions.

## Historical and forensic material

- [Intelligence history](history/intelligence/README.md) preserves versioned
  operational, provider, calibration, ML-policy, and training generations.
- [Reorganization history](reorg/README.md) indexes phase records, inventories,
  and migration forensics.
- [Experiment notes](experiments/) and [research notes](research_notes/) record
  particular studies and findings; verify their inputs and dates before reuse.

Historical paths and commands describe the repository at the time of the
recorded experiment. Current paths are governed by the architecture and
subsystem READMEs above.
