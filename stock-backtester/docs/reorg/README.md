# Reorganization history

This directory records how Reorg V1 changed the repository and why several
older paths still exist. For day-to-day work, start with the current project
documentation instead.

Start with:

- [Current project README](../../README.md)
- [Current documentation map](../README.md)
- [Current architecture](../architecture.md)
- [Research workflow](../research_workflow.md)
- [Outputs and artifacts](../output_policy.md)
- [Reorg V1 freeze boundary](REORG_V1_FREEZE.md)

## What lives here

- `PHASE*.md` files are historical records of individual migration slices.
- `REORG_STATUS.md` and `reorg_timeline.md` record accumulated phase history.
- inventory CSV/JSON files are snapshots from earlier phases and may no longer
  describe the live tree.
- `PHASE22_DOCUMENT_INVENTORY.csv` records the initial Phase 22 classification
  of every tracked Markdown document.
- forensics documents explain compatibility constraints and why historical
  files were kept.
- current compatibility contracts include
  [OUTPUT_CONTRACTS.md](OUTPUT_CONTRACTS.md),
  [SACRED_WORKFLOWS.md](SACRED_WORKFLOWS.md), and
  [OVERLAY_LINEAGE.md](OVERLAY_LINEAGE.md). The root directory review and
  intelligence archive are summarized by
  [PHASE25_ROOT_TOPOLOGY.md](PHASE25_ROOT_TOPOLOGY.md) and
  [PHASE25_OVERLAY_PRESERVATION.md](PHASE25_OVERLAY_PRESERVATION.md). The
  tracked archive and final root work are recorded in
  [PHASE25B_ROOT_PHYSICAL_CLEANUP.md](PHASE25B_ROOT_PHYSICAL_CLEANUP.md).
  The generated-output snapshot and its writer/reader map are recorded in
  [PHASE26_OUTPUT_TAXONOMY.md](PHASE26_OUTPUT_TAXONOMY.md) and its
  [machine-readable inventory](PHASE26_OUTPUT_INVENTORY.csv).
  The final re-entry audit, known follow-up work, extension rules, and
  validation results are recorded in
  [REORG_V1_FREEZE.md](REORG_V1_FREEZE.md).

The phase files remain here so their links and references keep working. You do
not need to read Phase 0 through Phase 21 to understand the current system.

## Validation tools

Repository-maintenance commands live under
[`tools/reorg/`](../../tools/reorg/README.md), not in this documentation
directory. Regenerate a machine-readable manifest with its documented tool;
an old inventory is not a substitute for inspecting the current tree.

## Why the history remains

Phase records, overlay lineage, output contracts, and investigation notes help
when repairing an old workflow or explaining why multiple implementations
coexist.
