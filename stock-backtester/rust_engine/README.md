# Rust Stress Engine

Purpose
-------

Rust provides bounded acceleration/stress testing for matrix-oriented research.
It is a separate computational regime from package-oriented Python workflows.

Current implementation
----------------------

The Cargo project and binaries live in this directory. Python preparation and
consumption scripts remain in `scripts/export_rust_*` and
`scripts/summarize_rust_stress_runs.py`.

Contracts
---------

Input/output paths and binary schemas are documented in
`docs/reorg/SACRED_WORKFLOWS.md` and `docs/reorg/OUTPUT_CONTRACTS.md`. Do not
move or rename them without compatibility validation.

Tests
-----

No Rust build is part of the offline topology pass. Use bounded existing smoke
commands only when their inputs are local and known.
