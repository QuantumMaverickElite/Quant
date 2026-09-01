# Quant research workspace

This repository is a quantitative research workspace. The main active system is
[stock-backtester](stock-backtester/README.md), which contains reusable Python
implementation, commands, research programs, tests, configuration, and
documentation.

## Start here

1. Read the [stock-backtester project map](stock-backtester/README.md).
2. Use its [documentation index](stock-backtester/docs/README.md) for current
   architecture, research workflow, outputs, and subsystem guides.
3. Use [reorganization history](stock-backtester/docs/reorg/README.md) only for
   migration archaeology.

## Root layout

| Path | Status |
| --- | --- |
| `stock-backtester/` | Main active quant research system |
| `dividend-capture/` | Separate historical research lane pending a dedicated ownership migration |
| `worker_ingest/` | Operational ingestion infrastructure, not a peer research project |
| `market_intelligence_*_overlay/` | Ignored/local historical overlays requiring preservation decisions before archival |

The last two categories may not appear in normal Git inventories. Do not move or
delete them based only on the root layout. Overlay lineage is documented in
[OVERLAY_LINEAGE.md](stock-backtester/docs/reorg/OVERLAY_LINEAGE.md).

No root-level lane should be inferred to be production authority merely because
it has its own directory.
