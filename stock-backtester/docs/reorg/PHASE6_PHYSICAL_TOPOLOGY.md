# Phase 6 physical topology

Phase 6 completed the first physical reduction of tracked source clutter. The
moves were user-performed and this pass repaired imports, metadata, and docs
around them without changing research behavior.

## Actual moves

- Five offline validation tests moved from `scripts/` to `tests/`.
- Six repository-maintenance tools moved from `scripts/` to `tools/reorg/`.
- The six-file historical ML-policy family moved into
  `src/backtester/intelligence/ml_policy/`.
- The four historical ML-policy command paths remain in `scripts/`.

## Compactness accounting

| Location | Before | After |
| --- | ---: | ---: |
| `scripts/` direct files | 179 | 168 |
| `tests/` direct files | 1 README | 6 files including README |
| `tools/reorg/` direct files | absent | 7 including README |
| `src/backtester/intelligence/` direct files | 55 | 49 |
| `src/backtester/intelligence/` direct entries | 55 | 50 including `ml_policy/` |
| `ml_policy/` direct files | absent | 7 including README and `__init__.py` |

The reduction is physical: tests and maintenance utilities no longer compete
visually with research commands, and ML-policy research has one obvious home.

## Compatibility

The historical command wrappers remain the supported user-facing boundary:

```text
scripts/apply_ml_policy_strength.py
scripts/validate_ml_policy_candidate.py
scripts/sweep_ml_policy_strength.py
scripts/permutation_test_ml_policy.py
```

Tracked imports and registry metadata now use
`backtester.intelligence.ml_policy.*`. No flat compatibility modules were
recreated because repository-wide search found only tracked internal consumers.

## Root and future ownership

`dividend-capture/` is explicitly not a permanent root peer. Future forensics
should separate reusable strategy code for
`src/backtester/strategies/dividend_capture/` from research/history under
`research/strategies/dividend_capture/`. It was not moved here.

Root overlays remain ignored historical patch bundles and require verified
hash/recoverability work before archival. `worker_ingest/` remains an
operational/cache concern requiring separate ownership analysis.

## Next physical targets

1. Remaining intelligence families: event/fact/outcome data, training/provider
   handling, operational fallback, and evaluation; group only after imports and
   authority are mapped.
2. Large-universe/mean-reversion script family; preserve its matrix and output
   contracts behind a small set of command wrappers.
3. Correlation/deformation runners, followed by allocator/Rust stress tooling
   once binary contracts have focused tests.

See [`ML_POLICY_SCRIPT_FAMILY.md`](ML_POLICY_SCRIPT_FAMILY.md),
[`AUTHORITATIVE_PATHS.md`](AUTHORITATIVE_PATHS.md), and the current subsystem
READMEs for ownership boundaries.
