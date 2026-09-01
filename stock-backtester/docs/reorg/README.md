# Reorganization history and forensics

This directory preserves the evidence and migration record for Reorg V1. It is
not the primary documentation surface for the current system.

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
- inventory CSV/JSON files capture bounded observations from earlier phases;
  they are not automatically current.
- `PHASE22_DOCUMENT_INVENTORY.csv` records the initial Phase 22 classification
  of every tracked Markdown document.
- forensics documents explain compatibility and preservation decisions.
- current compatibility contracts include
  [OUTPUT_CONTRACTS.md](OUTPUT_CONTRACTS.md),
  [SACRED_WORKFLOWS.md](SACRED_WORKFLOWS.md), and
  [OVERLAY_LINEAGE.md](OVERLAY_LINEAGE.md). The current root ownership and
  preservation decisions are summarized by
  [PHASE25_ROOT_TOPOLOGY.md](PHASE25_ROOT_TOPOLOGY.md) and
  [PHASE25_OVERLAY_PRESERVATION.md](PHASE25_OVERLAY_PRESERVATION.md). The
  tracked archive and final root work are recorded in
  [PHASE25B_ROOT_PHYSICAL_CLEANUP.md](PHASE25B_ROOT_PHYSICAL_CLEANUP.md).
  The current generated-artifact snapshot, writer/reader decisions, and freeze
  disposition are recorded in
  [PHASE26_OUTPUT_TAXONOMY.md](PHASE26_OUTPUT_TAXONOMY.md) and its
  [machine-readable inventory](PHASE26_OUTPUT_INVENTORY.csv).
  The final re-entry audit, deferred-debt register, extension rules, and
  validation boundary are recorded in
  [REORG_V1_FREEZE.md](REORG_V1_FREEZE.md).

The phase files remain physically here because moving them would create noisy
reference churn without improving the current authority map. Readers should not
need to read Phase 0 through Phase 21 to understand current architecture.

## Validation tools

Repository-maintenance commands live under
[`tools/reorg/`](../../tools/reorg/README.md), not in this documentation
directory. Machine-readable manifests should be regenerated only by their
documented tools; do not treat old inventory output as live discovery.

## Preservation rule

Historical does not mean disposable. Phase records, overlay lineage, output
contracts, and forensic notes remain useful when repairing compatibility or
explaining why multiple implementations coexist.
