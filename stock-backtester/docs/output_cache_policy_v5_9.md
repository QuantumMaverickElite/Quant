# Quant Storage, Cache, and Output Policy v5.9

This project has outgrown ad-hoc output folders. The goal is to keep the research reproducible without letting raw API payloads, curve dumps, bootstrap paths, plots, and failed runs clog the local disk.

## Two operating modes

### Historical research mode
Historical research can be heavy, but it should be occasional and compacted afterward.

Pipeline:

1. Fetch / merge / dedupe external sources.
2. Score sentiment and evidence once.
3. Build compact ticker-date features.
4. Train / validate walk-forward models.
5. Run Monte Carlo / permutation / policy sweeps on finalists.
6. Compact the run.
7. Push compact artifacts to a private artifact repository or remote storage.
8. Delete/archive bulky local intermediates.

### Live intraday mode
Live mode should be lightweight and bounded.

Pipeline:

1. Poll current-day sources for a bounded ticker universe.
2. Entity-resolve and dedupe by article hash.
3. Score sentiment/evidence only when the article hash is new.
4. Aggregate tiny ticker-time-window features.
5. Run inference using the latest promoted model.
6. Store only bounded raw evidence and compact feature snapshots.
7. Later, when forward returns are known, attach labels for the next offline retrain.

Important: day-of news can be used for inference immediately, but it cannot be supervised-trained immediately until the future outcome exists.

## Local retention rules

Keep locally by default:

- `all_monte_carlo_ranked.csv`
- `stress_manifest.csv`
- `manifest.csv`
- `status.txt`
- `run_long_training.sh`
- final summary CSV files
- top-N prediction parquet files for selected configs
- final equity/policy/permutation summaries
- compact feature stores
- docs and config files needed to reproduce the run

Archive or push remotely:

- selected top prediction parquet files
- important plots
- compact tarballs of finished runs
- official SEC/company evidence used for auditability
- compressed source bundles only when they are actually needed

Delete or regenerate locally:

- bootstrap path dumps
- spaghetti path dumps
- repeated curve CSVs
- trial-level Monte Carlo dumps
- frame-by-frame visualization exports
- old smoke runs that failed before producing summaries
- duplicated raw provider JSONL after compact features are built

## Cache rules

The live cache should be bounded by size and TTL.

Recommended default:

- live raw article payload TTL: 14 days
- research raw article payload TTL: 30 days
- derived ticker/date features: 2 years
- sentiment/evidence scores by article hash: keep longer because they prevent duplicate scoring
- official SEC/company records: keep longer or archive remotely

The model should not memorize raw articles forever. Long-term training rows should represent compact facts:

`ticker, as_of, source_kind, sentiment, novelty, event_type, official_confirmation, relevance, price_state, realized_label_later`

## Remote artifact repository policy

A private GitHub artifact repository is fine for compact artifacts: ranked summaries, manifests, configs, selected prediction files, and compressed bundles. Do not use normal Git history as an unlimited dump for huge raw payloads. If artifacts are large, use Git LFS, releases, object storage, or only push compact tarballs.

Recommended flow:

1. Compact run locally.
2. Review bundle size.
3. Copy bundle to the private artifact repo.
4. Commit and push.
5. Delete local heavy intermediates only after verifying the artifact exists remotely.

## New scripts in this overlay

- `scripts/audit_quant_outputs.py` scans output folders and creates a dry-run cleanup plan.
- `scripts/compact_intelligence_run.py` compacts a single intelligence training run into a small artifact bundle.
- `scripts/live_intelligence_cache.py` creates and maintains a bounded SQLite cache for deduped intraday/news evidence and features.
- `scripts/live_intraday_intelligence_loop.py` runs a lightweight poll/ingest loop around the existing fetcher.
- `scripts/archive_compact_artifact_to_git.py` copies compact bundles into a private artifact repo and optionally commits them.

All destructive actions default to dry-run/review. Deletion requires explicit flags.
