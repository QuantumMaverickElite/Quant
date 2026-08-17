# Phase 5 topology note

Phase 5 reduces re-entry cost without changing quantitative behavior. The
navigation spine is the repository root README → `stock-backtester/README.md`
→ subsystem READMEs, `scripts/README.md`, `configs/README.md`, and the docs
index.

The major physical issue remains `stock-backtester/scripts/` (178 direct files,
15 test-named files). Five tests were identified as clearly offline and ready to
move, but this managed workspace rejected creation of `stock-backtester/tests/`.
They therefore remain in place until a writable topology slice can use `git mv`.
The remaining test-named programs are data-dependent or synthetic smoke tools
and require separate classification before movement.

Root overlay directories are ignored/untracked and cannot be protected by Git.
No overlay was touched. A future, explicitly approved archival operation should
verify the lineage manifest and preserve bundles under a dedicated archive such
as `archive/overlays/verified/<overlay-name>/`; that destination is only a
proposal at this stage.

The combined research map is
[`research_notes/COMBINED_SIGNAL_RESEARCH.md`](../research_notes/COMBINED_SIGNAL_RESEARCH.md).
It records how baseline mean reversion can be compared with context,
correlation/deformation, volatility, and intelligence adjustments without
declaring an official baseline.
