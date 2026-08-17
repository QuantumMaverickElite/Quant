# Reorganization Control Room

This directory is the control room for the stock-backtester reorganization.

The reorganization rule is simple:

1. Measure before moving anything.
2. Preserve old script paths until replacement wrappers exist.
3. Protect sacred scripts with smoke tests and golden outputs.
4. Move code behind stable interfaces before changing behavior.
5. Archive overlays after their useful docs/code have been harvested.

## Phase 0 authority inventory

Run from the repository root:

```bash
python scripts/reorg_audit.py --out outputs/reorg_audit/latest
python scripts/reorg_sacred_smoke.py --manifest configs/sacred_scripts.json --dry-run
python scripts/reorg_phase0_inventory.py --root .
```

The Phase 0 control documents are:

- [REORG_STATUS.md](REORG_STATUS.md)
- [AUTHORITATIVE_PATHS.md](AUTHORITATIVE_PATHS.md)
- [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md)
- [SCRIPT_INVENTORY.md](SCRIPT_INVENTORY.md)
- [OUTPUT_CONTRACTS.md](OUTPUT_CONTRACTS.md)
- [OVERLAY_LINEAGE.md](OVERLAY_LINEAGE.md)
- [SACRED_WORKFLOWS.md](SACRED_WORKFLOWS.md)

The compact machine-readable manifests are the CSV/JSON files in this directory. They are deliberately source-control friendly and do not contain raw output trees.

## Later-phase checklist

After the audit report looks reasonable:

1. Resolve the `USER DECISION REQUIRED` items in `REORG_STATUS.md`.
2. Normalize artifact/storage behavior without moving source paths.
3. Add compatibility wrappers before any path move.
4. Run the Phase 0 tests, audit, and sacred smoke checks before and after each small change.
5. Only then start moving code into a domain-oriented package structure.
