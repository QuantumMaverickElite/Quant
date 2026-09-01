# Phase 25B root physical cleanup

Phase 25B converts the preservation plan into a tracked historical archive and
moves the contract-protected dividend research family into its research lane. It does not
move generated outputs or the operational `worker_ingest/` interface.

## Intelligence overlay archive

Archive commit `9b4409444d49ad31bd1809f8bf84a768b81c10a6` preserves 66 overlay
generations as 289 payload files under:

```text
archive/intelligence_overlays/repository_root/
archive/intelligence_overlays/stock_backtester_root/
```

The two provenance lanes prevent the three duplicate overlay names from
colliding. Together with the two archive READMEs, Git tracks 291 files under
`archive/`. The 10 old repository-root overlays and 56 old
stock-backtester-root overlays are intentionally absent.

Archive verification requires exactly 289 rows and 66 overlays, exact sizes and
hashes, no missing or extra payload files, aggregate SHA-256
`7225c8d7e31925e09ee00737d3e2becde81b09425a9e3d2cfb3ce74182278c47`,
and v2.6.2 document SHA-256
`37b9dc082c673ca814792f2fb17eb71faf9f3173d47ec6581464f0ff91fbaf58`.

The archive tool distinguishes lifecycle stages:

- `verify-sources` is a pre-removal source check and now fails clearly after a
  completed migration.
- `copy` requires valid sources, copies only manifest-authoritative payloads,
  verifies the archive, and writes the verification manifest.
- `verify` is archive-only and works after source deletion.
- `remove-sources` requires explicit confirmation, guarded paths, and archive
  verification before and after removal.

## Dividend-capture research

The 12 tracked root files comprise documentation/configuration and eight
programs across four research families: naive original-universe,
regime-filtered, long-only recovery, and PG-like-universe naive capture. The two
naive backtests are byte-identical but remain separate research generations.
Regime-filtered and long-only recovery are distinct methodologies. No tracked
caller imports this family, and no evidence supports package ownership or a
canonical generation.

Four deterministic contracts cover calendar alignment, `TradeResult` schema,
timezone handling, profile labels, shifted rolling regimes and boundaries,
long/short/skip behavior, output column order, recovery thresholds, and the two
long-only signal variants. Dependency-complete validation passed all four.

All 12 tracked files now live under
`stock-backtester/research/dividend_capture/`, and the contracts resolve that
location. Eleven moved files match their starting-HEAD blobs exactly; the moved
README differs only by the Phase 25B ownership and path documentation added
before and after relocation. All eight Python programs are byte-identical to
their starting blobs.

The remaining root `dividend-capture/` directory contains 60 ignored generated
output files (about 4.5 MB) plus empty, untracked, non-ignored `data/` and
`notes/` placeholders. No durable notes or data inputs were present. This is a
generated/local compatibility lane for Phase 26, not active source ownership.

## Root disposition

- `stock-backtester/`: active system.
- `archive/`: tracked historical preservation, not authority.
- `worker_ingest/`: intentionally retained operational interface.
- `research/dividend_capture/`: tracked historical research, with four distinct
  generations and no production promotion.
- repository-root `dividend-capture/`: generated/local compatibility state for
  Phase 26 only.
- `.git/`, `.venv/`, `.codex/`: intentional control/local state.

No stock-backtester output, dividend output, worker payload, provider, or
quantitative methodology changed in this phase.

Root-level source ownership is complete for Reorg V1. Output and data-policy
classification remains Phase 26 work rather than root topology debt.
