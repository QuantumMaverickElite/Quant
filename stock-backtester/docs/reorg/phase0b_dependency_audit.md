# Phase 0B Dependency Audit

Phase 0B extends the reorganization scaffold without moving production code.

It adds three audits:

1. `scripts/reorg_import_graph.py` — parses Python imports and reports internal dependencies, script-to-module edges, and likely missing internal imports.
2. `scripts/reorg_overlay_inventory.py` — inventories overlay directories, duplicate basenames, duplicate hashes, and likely promoted/canonical files.
3. `scripts/reorg_file_inventory.py` — classifies repository files as active code, script code, overlay code, docs, generated artifacts, archives, cache, or unknown.

Recommended run:

```bash
python scripts/reorg_import_graph.py --out outputs/reorg_audit/latest
python scripts/reorg_overlay_inventory.py --out outputs/reorg_audit/latest
python scripts/reorg_file_inventory.py --out outputs/reorg_audit/latest
```

These reports are diagnostic only. They should be committed only if you want to preserve a snapshot. Generated audit outputs under `outputs/` should normally remain untracked.
