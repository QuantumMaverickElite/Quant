# Parameter / Configuration Registry

Phase 4 extends the read-only experiment registry with typed configuration
metadata and validated in-memory configurations. The implementation remains
stdlib-first in `src/backtester/experiments.py`.

## Two distinct layers

- `ParameterSpec` describes a parameter: type, current default, owner,
  provenance, CLI flag, units, supported modes, and constraints.
- `ExperimentConfig` assigns values to a registered experiment. It can be
  serialized to deterministic JSON and validated without running anything.

The current defaults are copied from the registered command parser defaults.
Existing scripts remain authoritative and were not rewritten to consume this
model.

## Configuration modes

- `FIXED`: one validated value; this is the default for scalar pilot parameters.
- `CHOICE`: an explicit finite list. The ML-policy sweep candidate lists are
  represented this way because their current source is an explicit CLI list.
- `SWEEP`: a typed start/stop/step specification is modeled and validated, but
  no values or combinations are executed.
- `RANDOM`: `uniform`, `integer_uniform`, and `choice` specifications are
  modeled and validated, but no sampling occurs.

The model rejects wrong types, unknown parameters, unsupported modes, empty
choices, zero or directionally invalid sweep steps, and invalid distributions.

## CLI

```bash
PYTHONPATH=src python -m backtester.experiments config intelligence.ml_policy.permutation
PYTHONPATH=src python -m backtester.experiments config intelligence.ml_policy.permutation --set permutations=5000
PYTHONPATH=src python -m backtester.experiments config signals.mean_reversion.peer_spread_baseline --json
```

`config` is read-only. `--set` creates an in-memory validated override and
never invokes the experiment command.

## Provenance

Pilot scalar defaults are marked `CLI_DEFAULT`, with the parser symbol and CLI
flag recorded. Numerical safety ranges are not invented. Inputs/outputs remain
path metadata rather than executable path resolution.

## Future boundary

The JSON shape is intended for future CLI, planning, run-manifest, stress-test,
and native C operator-console consumers. This phase does not implement plan,
run, sweeps, random sampling, process orchestration, run history, or UI code.
