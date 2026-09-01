# Overlay Lineage and Preservation

Machine-readable source: [overlay_lineage.csv](overlay_lineage.csv).

## Findings

- 56 `market_intelligence_*_overlay` directories exist under `stock-backtester`.
- 10 additional overlay directories exist at repository root.
- These directories are ignored by Git and are therefore not protected by branch rollback.
- Overlay files are patch-delivery source/documentation, not runtime imports.
- Version documents contain explicit copy commands showing promotion from overlay paths into canonical `src/`, `scripts/`, and `docs/` paths.
- Many overlay files are identical to canonical files; others differ because canonical code continued evolving.
- `market_intelligence_v2_6_2_overlay/docs/market_intelligence_v2_6_2.md` has no tracked canonical counterpart, including under `docs/history/intelligence/` and is recorded as `CANONICAL MISSING` in the manifest.

## Relationship meanings

- `IDENTICAL`: overlay hash equals the candidate canonical destination.
- `DIFFERENT`: both files exist but content differs; preserve and review the delta.
- `CANONICAL MISSING`: no candidate canonical destination exists.
- `DESTINATION UNCERTAIN`: path shape does not identify a safe canonical destination.

## Preservation rule

Do not delete, move, rewrite, or promote any overlay during Phase 0. Fully identical overlays may become archival candidates only after their hashes, documentation, and reproducibility value have been recorded externally or in a future preservation commit.

Git history is sufficient evidence for currently tracked canonical files, but it is not a complete substitute for preserving ignored overlay contents.

## User decision required

Choose whether preserved overlays will live in the repository, in an external artifact store, or as verified compact archives plus tracked manifests.
