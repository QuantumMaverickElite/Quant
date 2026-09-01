# Repository reorganization tools

These scripts audit repository structure, verify archived files, and run
reorganization smoke checks. They are maintenance utilities, not part of the
trading or research pipeline.

| Tool | Purpose | Writes? | Typical invocation |
| --- | --- | --- | --- |
| `reorg_audit.py` | architecture/audit report | yes, report files | `python tools/reorg/reorg_audit.py --out outputs/reorg_audit/latest` |
| `reorg_file_inventory.py` | classify tracked/local files | yes, report files | `python tools/reorg/reorg_file_inventory.py --out outputs/reorg_audit/latest` |
| `reorg_import_graph.py` | inspect internal import relationships | yes, report files | `python tools/reorg/reorg_import_graph.py --out outputs/reorg_audit/latest` |
| `reorg_overlay_inventory.py` | compare overlay files and hashes | yes, report files | `python tools/reorg/reorg_overlay_inventory.py --out outputs/reorg_audit/latest` |
| `reorg_phase0_inventory.py` | rebuild the Phase 0 manifests from their original scope | yes, manifests/docs | `python tools/reorg/reorg_phase0_inventory.py --root .` |
| `reorg_sacred_smoke.py` | dry-run or execute configured sacred checks | potentially; command-dependent | `python tools/reorg/reorg_sacred_smoke.py --manifest configs/sacred_scripts.json --dry-run` |
| `archive_intelligence_overlays.py` | copy and byte-verify the Phase 25 ignored overlays in their tracked archive | only for explicit `copy` / confirmed removal | `python tools/reorg/archive_intelligence_overlays.py verify` |

The inventory tools are read-only with respect to source/data and write only their
requested reports. Sacred smoke is potentially executing and must remain
offline/non-destructive; skip commands that require providers, downloads, or
large research runs. The overlay archive tool only handles paths listed in the
Phase 25 manifest: `copy` preserves all 289 rows and `remove-sources` refuses to
run unless both archive verification and an explicit confirmation flag pass.
After the completed migration, normal validation is archive-only `verify`;
`verify-sources` is the pre-removal lifecycle check and now fails because the
audited source overlays are intentionally absent.
