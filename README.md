# Quant research workspace

This repository is a quantitative research workspace. The main active system is
[stock-backtester](stock-backtester/README.md), which contains reusable Python
implementation, commands, research programs, tests, configuration, and
documentation.

## Start here

1. Read the [stock-backtester project map](stock-backtester/README.md).
2. Use its [documentation index](stock-backtester/docs/README.md) for current
   architecture, research workflow, outputs, and subsystem guides.
3. Use [reorganization history](stock-backtester/docs/reorg/README.md) when you
   need to understand an older path or migration decision.

## What is at the repository root

| Path | Status |
| --- | --- |
| `stock-backtester/` | Main active quant research system |
| `archive/` | Older intelligence versions kept so earlier experiments can be inspected or recovered; nothing here runs as part of the current system |
| `dividend-capture/` | Result files from the older dividend research; the research code itself now lives in `stock-backtester/research/dividend_capture/` |
| `worker_ingest/` | Local files exchanged with the Chromebook worker; existing parsers read this exact root path |
| `.codex/`, `.venv/` | Local tooling/environment state, not repository projects |

Dividend research code lives under
[`stock-backtester/research/dividend_capture/`](stock-backtester/research/dividend_capture/README.md).
Its 60 historical output files stay at `dividend-capture/outputs/` because the
research commands still document that path and an exact rebuild from live
market data is not guaranteed. The worker cache and dividend results are local
generated files, so they do not appear in normal Git inventories.

Old intelligence overlays are stored under `archive/`; their former ignored
directories have been removed. See the
[reorganization history](stock-backtester/docs/reorg/README.md) for migration
details and the [output policy](stock-backtester/docs/output_policy.md) before
moving or deleting generated files.
