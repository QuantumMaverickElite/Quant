# Overlay Lineage and Preservation

Original machine-readable source: [overlay_lineage.csv](overlay_lineage.csv).
The Phase 25 live preservation decision is recorded in
[PHASE25_OVERLAY_PRESERVATION.md](PHASE25_OVERLAY_PRESERVATION.md).

## Phase 0 findings

- The Phase 0 scan found 56 `market_intelligence_*_overlay` directories under
  `stock-backtester` and 10 additional overlay directories at repository root.
- Those source directories were ignored by Git and therefore were not protected
  by branch rollback before the Phase 25B archive migration.
- Overlay files are patch-delivery source/documentation, not runtime imports.
- Version documents contain explicit copy commands showing promotion from overlay paths into canonical `src/`, `scripts/`, and `docs/` paths.
- Many overlay files are identical to canonical files; others differ because canonical code continued evolving.
- `market_intelligence_v2_6_2_overlay/docs/market_intelligence_v2_6_2.md` has no tracked canonical counterpart, including under `docs/history/intelligence/` and is recorded as `CANONICAL MISSING` in the manifest.

The Phase 0 destination columns reflect the paths that existed when that scan
ran. Phase 22 later moved historical intelligence documents and research
commands, so those destination strings are historical evidence rather than a
live path map. Source-file hashes remain preservation evidence.

## Relationship meanings

- `IDENTICAL`: overlay hash equals the candidate canonical destination.
- `DIFFERENT`: both files exist but content differs; preserve and review the delta.
- `CANONICAL MISSING`: no candidate canonical destination exists.
- `DESTINATION UNCERTAIN`: path shape does not identify a safe canonical destination.

## Preservation rule

The 66 overlays were copied into the tracked, human-readable
`archive/intelligence_overlays/` tree and byte-verified before the old ignored
source directories were removed. Do not restore the old locations or promote
archive contents into current implementation.

Git history is sufficient evidence for currently tracked canonical files, but it is not a complete substitute for preserving ignored overlay contents.

## Current verification

Run `python tools/reorg/archive_intelligence_overlays.py verify` from the Quant
repository root. Archive verification intentionally does not depend on the
removed source overlays.
