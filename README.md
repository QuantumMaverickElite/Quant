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
| `archive/` | Tracked, human-readable historical intelligence-overlay preservation; not runtime or research authority |
| `dividend-capture/` | Preserved historical dividend output compatibility state plus empty local `data/` and `notes/` placeholders; no tracked research source |
| `worker_ingest/` | Ignored/local operational cache and synchronization interface used by tracked Chromebook parsers; its root path is a compatibility contract |
| `.codex/`, `.venv/` | Local tooling/environment state, not repository projects |

Tracked dividend research lives under
[`stock-backtester/research/dividend_capture/`](stock-backtester/research/dividend_capture/README.md).
Phase 26 retained the 60-file root dividend output tree because its four
historical generations are not proven exactly regenerable, its path is
documented by the migrated research commands, and the existing
`stock-backtester/outputs/dividend/` lane has different lineage. The worker
cache and dividend output state do not appear in normal Git inventories.
The 66 former intelligence overlays are now recoverable from the tracked
archive; the old ignored source directories are intentionally absent. Root
decisions and overlay preservation evidence are in the
[Phase 25 root topology record](stock-backtester/docs/reorg/PHASE25_ROOT_TOPOLOGY.md)
and [Phase 25B physical-cleanup record](stock-backtester/docs/reorg/PHASE25B_ROOT_PHYSICAL_CLEANUP.md).
Current output classification and retention policy are in the
[Phase 26 taxonomy](stock-backtester/docs/reorg/PHASE26_OUTPUT_TAXONOMY.md).

No root-level lane should be inferred to be production authority merely because
it has its own directory.
