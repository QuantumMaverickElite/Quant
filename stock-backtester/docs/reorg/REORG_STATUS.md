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
7. Phase 5: domain-oriented package restructuring.
8. Phase 6: compatibility, reproducibility, and deprecation validation.

## Candidate cheap wins

- Add a current-workflow index and owner/status fields to the manifests.
- Add offline contract tests for sacred commands and Rust matrix schemas.
- Define official compact baseline manifests before touching large outputs.
- Reconcile dependency specifications in a separate, explicitly approved task.

## User decisions required

- Promote or retain the current feature branch as the reorganization baseline.
- Decide whether heuristic intelligence remains operational.
- Select official research baselines and overlay preservation destination.
- Decide long-term ownership of dividend capture and remote worker workflows.
