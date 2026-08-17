# Reorganization Status Board

## Phase 0 status

Completed on `reorg/phase0-authority-inventory`:

- Existing audit policy now excludes `.vnev` as well as `.venv` and other cache/build trees.
- Import-graph audit no longer parses ignored overlays unless `--include-overlays` is explicitly requested.
- Deterministic subsystem, script, output-contract, physical-inventory, and overlay-lineage manifests were generated from bounded local evidence.
- Current architecture, authority, sacred workflows, and preservation rules are documented.
- Offline fixture tests cover role classification, overlay comparison, missing canonical destinations, and deterministic contract ordering.

## Phase 1 status

- Completed the first behavior-preserving shared-infrastructure extraction: common CSV/Parquet table I/O now lives in `src/backtester/utils/tables.py`.
- Migrated four representative ML-policy research scripts and preserved the existing `backtester.intelligence.candidates.read_table` / `write_table` import paths as compatibility aliases.
- Remaining table-I/O helpers were intentionally not mass-migrated; their semantics and ownership require separate review.

## Phase 2 status

- Completed the first script-family extraction for the historical ML-policy research line.
- The four original top-level paths remain compatibility wrappers with symbol re-exports and unchanged CLI parsers/defaults.
- Shared column detection now has one family-owned helper; workflow-specific statistical and policy logic remains separate.
- No event-learning, operational intelligence, allocator, or production behavior was changed.

## Phase 3 status

- Added a stdlib-first typed experiment/component/pipeline/command registry at `src/backtester/experiments.py`.
- Registered the four historical ML-policy experiments plus a documented mean-reversion baseline, large-universe pipeline, and deformation-weighted research entry.
- Added deterministic human-readable and JSON discovery commands: `list`, `describe`, and `validate`.
- Registry discovery is metadata-only; no experiment execution, planning, stress orchestration, or UI was added.

## Phase 4 status

- Evolved the experiment registry with typed `ParameterSpec`, `ExperimentConfig`, fixed/choice/sweep/random value models, provenance metadata, deterministic JSON, and validated in-memory overrides.
- Added read-only `config` discovery output; no experiment command is invoked and no existing CLI default was changed.
- Added stdlib-only configuration tests covering type errors, choices, sweep validation, random distribution metadata, overrides, and JSON round trips.

## Phase 5 status — repository topology

- Added a repository-root and `stock-backtester/` navigation spine with direct
  links to major subsystem homes, tests, configs, outputs, and runbooks.
- Added compact READMEs for signals, analytics, context, correlation/deformation,
  engines, intelligence, Rust, configs, and scripts.
- Added a current/research/history documentation index and a combined-signal
  research map covering baseline, context, deformation, risk, and intelligence
  adjustment layers.
- Classified the 15 `scripts/test_*.py` files. Five are clearly offline
  control-plane/contract tests; no test was moved because the managed workspace
  is read-only and could not create the requested `tests/` directory. This is a
  documented follow-up, not a silent path change.
- No production or research executable was moved, renamed, or behaviorally
  changed. Root and `stock-backtester` overlay bundles remain untouched.

## Preservation blockers

- Overlay directories are ignored and not recoverable from normal Git history.
- The v2.6.2 overlay documentation has no canonical destination.
- Existing output trees contain both regenerable intermediates and research evidence; official baselines are not yet identified.
- The operational heuristic intelligence path and event-learning research path coexist.

## Explicitly untouched

No production algorithms, strategy behavior, signal formulas, allocators, intelligence behavior, workers, Rust behavior, output schemas, data files, overlays, historical backtests, or generated output trees were moved, deleted, or rewritten. The only import changes are the selected table-I/O compatibility imports described above.

## Future sequence

1. Phase 0: authority, preservation, and contracts — completed.
2. Phase 1A: shared table-I/O extraction — completed by this slice.
3. Phase 1B: artifact/storage behavior normalization; no deletion until manifests and baselines exist.
4. Phase 2: additional shared infrastructure extraction behind compatibility interfaces.
5. Phase 3: gradual command/pipeline/experiment separation.
6. Phase 4: historical and overlay archival after preservation verification.
7. Phase 5: repository topology/navigation — documentation completed; physical
   test move remains blocked by workspace permissions.
8. Phase 6: domain-oriented package restructuring.
9. Phase 7: compatibility, reproducibility, and deprecation validation.

## Candidate cheap wins

- Add a current-workflow index and owner/status fields to the manifests.
- Add offline contract tests for sacred commands and Rust matrix schemas.
- Define official compact baseline manifests before touching large outputs.
- Reconcile dependency specifications in a separate, explicitly approved task.
- Require new research experiments to document ownership, purpose, inputs, outputs, parameters, command/runner, and test or baseline evidence before registry integration.

## User decisions required

- Promote or retain the current feature branch as the reorganization baseline.
- Decide whether heuristic intelligence remains operational.
- Select official research baselines and overlay preservation destination.
- Decide long-term ownership of dividend capture and remote worker workflows.
