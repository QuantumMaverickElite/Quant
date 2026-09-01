# Overlay Lineage and Preservation

Original machine-readable source: [overlay_lineage.csv](overlay_lineage.csv).
The Phase 25 live preservation decision is recorded in
[PHASE25_OVERLAY_PRESERVATION.md](PHASE25_OVERLAY_PRESERVATION.md).

## Findings

- 56 `market_intelligence_*_overlay` directories exist under `stock-backtester`.
- 10 additional overlay directories exist at repository root.
- These directories are ignored by Git and are therefore not protected by branch rollback.
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

Do not delete, move, rewrite, or promote any overlay without a verified archive
destination. Phase 25 found only a small fully duplicated subset; all overlays
remain in place because no archive destination was authorized and moving only a
subset would not resolve the preservation problem.

Git history is sufficient evidence for currently tracked canonical files, but it is not a complete substitute for preserving ignored overlay contents.

## User decision required

Choose whether preserved overlays will live in the repository, in an external artifact store, or as verified compact archives plus tracked manifests.
