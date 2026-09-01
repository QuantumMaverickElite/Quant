# Historical intelligence overlays

This tracked archive preserves the complete meaningful source/document content
of the 66 ignored `market_intelligence_*_overlay` delivery bundles inventoried
in Phase 25. It excludes only `__pycache__/` and `.pyc` files, which were outside
the Phase 25 preservation manifest.

Two origin lanes prevent same-named overlays from colliding:

- `repository_root/` contains overlays formerly located directly under the
  Quant repository root.
- `stock_backtester_root/` contains overlays formerly located directly under
  `stock-backtester/`.

Each overlay retains its original directory name and internal relative paths.
The archive is historical evidence, not runtime or package authority. Current
implementation remains under `stock-backtester/src/`, commands under
`stock-backtester/scripts/`, and current research under
`stock-backtester/research/`.

Provenance, source hashes, relationship classifications, and archive
verification are recorded in:

- [`PHASE25_OVERLAY_PRESERVATION.csv`](../../stock-backtester/docs/reorg/PHASE25_OVERLAY_PRESERVATION.csv)
- [`PHASE25_OVERLAY_PRESERVATION.md`](../../stock-backtester/docs/reorg/PHASE25_OVERLAY_PRESERVATION.md)
- [`PHASE25B_OVERLAY_ARCHIVE_VERIFICATION.csv`](../../stock-backtester/docs/reorg/PHASE25B_OVERLAY_ARCHIVE_VERIFICATION.csv)
- [`PHASE25B_ROOT_PHYSICAL_CLEANUP.md`](../../stock-backtester/docs/reorg/PHASE25B_ROOT_PHYSICAL_CLEANUP.md)
