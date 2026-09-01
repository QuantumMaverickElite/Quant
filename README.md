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

## Root layout and ownership

| Path | Status |
| --- | --- |
| `stock-backtester/` | Main active quant research system |
| `dividend-capture/` | Tracked, standalone historical strategy research; intentionally retained until its numerical behavior and ignored outputs have migration contracts |
| `worker_ingest/` | Ignored/local operational cache and synchronization interface used by tracked Chromebook parsers; its root path is a compatibility contract |
| `market_intelligence_*_overlay/` | Ignored/local historical delivery bundles; preserved in place because most contain content that differs from tracked canonical files |
| `.codex/`, `.venv/` | Local tooling/environment state, not repository projects |

The worker cache and overlays do not appear in normal Git inventories and are
not recoverable from a branch checkout. Do not move or delete them based only
on the root layout. Root decisions and overlay preservation evidence are in the
[Phase 25 root topology record](stock-backtester/docs/reorg/PHASE25_ROOT_TOPOLOGY.md)
and [overlay preservation manifest](stock-backtester/docs/reorg/PHASE25_OVERLAY_PRESERVATION.md).

No root-level lane should be inferred to be production authority merely because
it has its own directory.
