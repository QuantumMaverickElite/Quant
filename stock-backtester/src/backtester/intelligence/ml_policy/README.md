# ML policy

## Purpose

Historical ML-policy research around confidence adjustments, candidate
validation, strength/cap sweeps, and permutation testing.

## Status and boundary

`ACTIVE RESEARCH / HISTORICAL RESEARCH TOOLING`.

This package is explicitly not:

- operational heuristic intelligence;
- current event-learning/LLM authority; or
- allocator authority.

## Modules

- `common.py` — shared column detection and table helpers.
- `application.py` — apply policy strength and caps.
- `validation.py` — candidate validation and bootstrap diagnostics.
- `sweep.py` — documented strength/cap studies.
- `permutation.py` — within-date permutation null testing.

## Historical commands

The supported compatibility entry points remain:

```text
scripts/apply_ml_policy_strength.py
scripts/validate_ml_policy_candidate.py
scripts/sweep_ml_policy_strength.py
scripts/permutation_test_ml_policy.py
```

## Inputs, outputs, and tests

Inputs are saved prediction/training tables under
`outputs/intelligence/training_runs/`. Results remain under that existing output
contract, including policy, validation, sweep, and permutation summaries.

Offline compatibility/regression coverage is in
`tests/test_ml_policy_family.py`. Dependency-sensitive tests should run from the
project environment with `PYTHONPATH=src`.
