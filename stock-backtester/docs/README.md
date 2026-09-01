# Documentation guide

Start here for current project documentation. Older research notes and
reorganization records are kept separately for reference.

## Start here

| Topic | Document |
| --- | --- |
| Repository navigation and quick start | [Project README](../README.md) |
| Current architecture and code layout | [Architecture](architecture.md) |
| Large-universe pipeline | [Large-universe runbook](large_universe_pipeline.md) |
| Research lifecycle and benchmark discipline | [Research workflow](research_workflow.md) |
| Generated outputs and artifacts | [Output policy](output_policy.md) |
| Reproducibility principles | [Reproducibility](reproducibility.md) |
| Intelligence code and current status | [Intelligence README](../src/backtester/intelligence/README.md) |
| Event-learning research | [Event-learning README](../research/event_learning/README.md) |
| Experiment/config registry | [Experiment registry](reorg/EXPERIMENT_REGISTRY.md) and [parameter registry](reorg/PARAMETER_CONFIG_REGISTRY.md) |
| Offline tests | [Tests README](../tests/README.md) |

Subsystem-local READMEs under `src/backtester/`, `research/`, `scripts/`,
`configs/`, and `rust_engine/` provide the next level of detail.

## More guides

- [System guides](systems/) — market state, entropy, volatility, regimes,
  options, dividend-capture context, and matrix backends.
- [Strategy math](strategy_math.md) — mathematical definitions and formulas.
- [Intelligence storage policy](intelligence/storage_policy.md).
- [Output contracts](reorg/OUTPUT_CONTRACTS.md) and
  [sacred workflows](reorg/SACRED_WORKFLOWS.md).

Experiment and research notes describe particular studies. Check their dates
and inputs before using them as a starting point.

## Historical and forensic material

- [Intelligence history](history/intelligence/README.md) preserves versioned
  operational, provider, calibration, ML-policy, and training generations.
- [Reorganization history](reorg/README.md) indexes phase records, inventories,
  and migration forensics.
- [Experiment notes](experiments/) and [research notes](research_notes/) record
  particular studies and findings; verify their inputs and dates before reuse.

Historical paths and commands reflect the repository when the experiment ran.
For current paths, use the architecture guide and subsystem READMEs above.
