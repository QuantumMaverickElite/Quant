# Reorganization Timeline

## Phase 0: Audit and freeze

Estimated: 1-2 focused sessions.

Deliverables:

- repo audit report
- sacred scripts manifest
- first smoke-test harness
- branch created for reorganization
- no behavior changes

## Phase 1: Scaffolding

Estimated: 1-2 focused sessions.

Deliverables:

- `backtester.core` interfaces
- `backtester.math_core` package skeleton
- module registry
- docs explaining target architecture
- still no behavior changes

## Phase 2: Script stabilization

Estimated: 2-4 sessions.

Deliverables:

- categorize top-level scripts
- choose sacred scripts
- create wrappers for any moved scripts
- establish golden output files/hashes for key workflows

## Phase 3: Overlay extraction/archive

Estimated: 2-5 sessions.

Deliverables:

- identify latest useful overlay code
- merge only useful code into `src/backtester`
- move overlay docs to changelog/research notes
- archive or delete repeated overlay directories after branch safety

## Phase 4: Mathematical abstraction layer

Estimated: 1-2 weeks.

Deliverables:

- Kalman/state-space module
- RMT/spectral module
- Wasserstein/optimal-transport module
- HRP/allocation module
- shared feature/risk output schema

## Phase 5: Documentation rewrite

Estimated: 2-4 sessions.

Deliverables:

- architecture overview
- active workflows
- reproducibility guide
- deprecated docs moved to changelog/archive
