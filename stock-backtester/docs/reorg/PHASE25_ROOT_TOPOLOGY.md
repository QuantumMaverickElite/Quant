# Phase 25 root topology and preservation

Phase 25 assigns explicit ownership to every direct repository-root lane. It
does not move generated outputs, quantitative implementation, ignored overlays,
or external worker state.

## Root ownership

| Path | Classification | Decision | Evidence |
| --- | --- | --- | --- |
| `stock-backtester/` | active main project | resolved | reusable implementation, commands, research, tests, configuration, and current docs |
| `dividend-capture/` | historical strategy research | explicitly deferred | tracked standalone scripts, no tests, network data acquisition, four methodologies/universes, ignored outputs, no active stock-backtester imports |
| `worker_ingest/` | operational infrastructure / generated local cache | intentionally retained | ignored and not Git-recoverable; tracked parsers use its exact absolute root path |
| root `market_intelligence_*_overlay/` | ignored historical delivery bundles | preserved in place | nine of ten root overlays contain at least one file different from current tracked counterparts |
| `stock-backtester/market_intelligence_*_overlay/` | ignored historical delivery bundles | preserved in place | most contain differing content; one document has no tracked counterpart |
| `.codex/` | generated/local tooling | intentionally retained | ignored local state, not a project lane |
| `.venv/` | generated/local environment | intentionally retained | local dependency environment, not tracked ownership |
| `.git/`, `.gitignore`, `README.md` | repository control/navigation | resolved | appropriate repository-root contents |

No `archive/` directory was created because no ignored content was moved and no
durable archive destination was selected.

## Dividend-capture decision

`dividend-capture/` contains 12 tracked files and 72 physical files (about 4.6
MB including ignored outputs). Its eight programs implement and visualize four
standalone experiment variants: original-universe naive capture,
regime-filtered capture, long-only recovery, and PG-like-universe naive capture.
They use their own dependency file, `yfinance`, and working-directory-relative
input/output conventions. No tracked stock-backtester code imports this lane;
the similarly named event-strategy implementation is not evidence of
equivalence.

Decision: `EXPLICITLY_DEFER`. A later migration needs deterministic numerical
contracts, an authority decision across the variants, command/path compatibility,
and an output-ownership manifest. Moving it now would turn a topology phase into
a quantitative refactor.

## Worker-ingest decision

The ignored `worker_ingest/` tree is about 3.7 MB and contains 145 observed
payload files: 128 JSON and 17 XML files under `chromebook/cache/` and
`chromebook/outputs/`. It contains synchronized cache/result state, not tracked
implementation. Its aggregate path-and-file hash at inventory time was:

```text
accd555140157c8f34ea1f8bb5d1211c8aa8056a8ee8d00b2301e880f0ef19ed
```

Tracked `parse_cbworker_news_sources.py` and
`parse_cbworker_yahoo_chart.py` consume
`~/projects/quant/worker_ingest/chromebook`. Separately, worker dispatch scripts
package a small remote tree under `~/quant-worker`, use SSH/SCP, and sync current
job results to `outputs/intelligence/worker_results/`. Credential files and the
remote machine were not inspected.

Decision: `KEEP_ROOT_AS_OPERATIONAL_INTERFACE`. The exact local root path is a
compatibility contract. Moving it offers little implementation-ownership payoff
and would break parsers unless an explicit migration/adapter is designed.

## Overlay decision

The 66 ignored overlays and 289 source/document files remain untouched. See the
[preservation manifest](PHASE25_OVERLAY_PRESERVATION.md) for hashes, live
comparison totals, and reconstruction requirements.

## Output boundary for Phase 26

`stock-backtester/outputs/` was inspected read-only and is about 1.5 GB across
34 top-level directories. The largest observed categories are intelligence
(about 480 MB), signals (296 MB), threshold rebalance (179 MB), correlation
(114 MB), Rust stress (88 MB), and cache (86 MB). Worker-derived artifacts also
exist under `outputs/worker_ingest/` and `outputs/intelligence/worker_results/`.

Phase 26 must preserve input/output paths used by the dividend experiments,
worker parsers, event-learning commands, Rust contracts, and baseline reports.
No output file or directory was moved or rewritten in this phase.

## Root freeze disposition

| Former problem | Disposition |
| --- | --- |
| ambiguous active project | `RESOLVED`: stock-backtester is the active main system |
| dividend capture | `EXPLICITLY_DEFERRED` with contract prerequisites |
| worker ingest | `INTENTIONALLY_RETAINED` as an operational interface |
| ignored overlays | `BLOCKED` on archive destination; preservation evidence recorded |
| generated/local tooling | `INTENTIONALLY_RETAINED` and labeled non-project state |

No root ownership remains unknown. Physical compactness is deferred where it
would conflict with recoverability or an external path contract.
