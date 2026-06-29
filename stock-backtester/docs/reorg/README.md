# Reorganization Control Room

This directory is the control room for the stock-backtester reorganization.

The reorganization rule is simple:

1. Measure before moving anything.
2. Preserve old script paths until replacement wrappers exist.
3. Protect sacred scripts with smoke tests and golden outputs.
4. Move code behind stable interfaces before changing behavior.
5. Archive overlays after their useful docs/code have been harvested.

## Phase 0 checklist

Run from the repository root:

```bash
python scripts/reorg_audit.py --out outputs/reorg_audit/latest
python scripts/reorg_sacred_smoke.py --manifest configs/sacred_scripts.json --dry-run
```

Then edit `configs/sacred_scripts.json` and fill in the commands that must keep working.

## Phase 1 checklist

After the audit report looks reasonable:

1. Create a branch: `git switch -c reorg/phase0-audit-scaffold`
2. Commit this scaffold.
3. Add sacred scripts to `configs/sacred_scripts.json`.
4. Run smoke tests.
5. Only then start moving code into the new package structure.
