# Intelligence overlay history

Original machine-readable source: [overlay_lineage.csv](overlay_lineage.csv).
The Phase 25 archive plan is recorded in
[PHASE25_OVERLAY_PRESERVATION.md](PHASE25_OVERLAY_PRESERVATION.md).

## Phase 0 findings

- The Phase 0 scan found 56 `market_intelligence_*_overlay` directories under
  `stock-backtester` and 10 additional overlay directories at repository root.
- Those source directories were ignored by Git and therefore were not protected
  by Git before the Phase 25B archive migration.
- Overlay files are patch-delivery source/documentation, not runtime imports.
- Version documents contain explicit copy commands showing promotion from overlay paths into canonical `src/`, `scripts/`, and `docs/` paths.
- Many overlay files are identical to canonical files; others differ because canonical code continued evolving.
- `market_intelligence_v2_6_2_overlay/docs/market_intelligence_v2_6_2.md` has no tracked canonical counterpart, including under `docs/history/intelligence/` and is recorded as `CANONICAL MISSING` in the manifest.

The Phase 0 destination columns reflect the paths that existed when that scan
ran. Phase 22 later moved historical intelligence documents and research
commands, so those destination strings describe the old layout rather than the
current tree. The source-file hashes still verify the archived copies.

## Relationship meanings

- `IDENTICAL`: overlay hash equals the candidate canonical destination.
- `DIFFERENT`: both files exist but content differs; preserve and review the delta.
- `CANONICAL MISSING`: no candidate canonical destination exists.
- `DESTINATION UNCERTAIN`: path shape does not identify a safe canonical destination.

## Where the overlays are now

The 66 overlays were copied into `archive/intelligence_overlays/` and
byte-verified before the old ignored directories were removed. The archive is
for inspecting or recovering earlier versions, not for runtime imports or new
development.

Git history covers files that were already tracked, but the archive was needed
to retain ignored overlay files that Git could not recover.

## Current verification

Run `python tools/reorg/archive_intelligence_overlays.py verify` from the Quant
repository root. Archive verification intentionally does not depend on the
removed source overlays.
