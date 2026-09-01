# Market Intelligence v5.1 - Evidence Graph and Orthogonal News Scoring

This overlay adds a lightweight evidence graph to prevent repeated articles about the same event from being counted as separate independent signals.

## What Changed

- `src/backtester/intelligence/evidence_graph.py`
  - Clusters extracted claims into event groups.
  - Scores source diversity, duplicate support, official confirmation, social-only risk, and contradiction risk.
  - Assigns an `orthogonal_weight` so duplicate claims share one event-level impact.

- `src/backtester/intelligence/schemas.py`
  - Adds event metadata to `EvidenceClaim`: `event_id`, `duplicate_count`, `independent_source_count`, `trust_score`, `source_diversity`, `orthogonal_weight`, and contradiction fields.

- `src/backtester/intelligence/intelligence_engine.py`
  - Runs claim extraction through the evidence graph before sentiment/regime scoring.
  - Adds model features such as `raw_claim_count`, `orthogonal_event_count`, `duplicate_claim_count`, `avg_event_trust`, and `avg_source_diversity`.

- `scripts/inspect_evidence_graph.py`
  - Smoke-test CLI for inspecting duplicate-aware event clusters.

## Smoke Test

Apply from the repo root:

```bash
cp market_intelligence_v5_1_evidence_overlay/src/backtester/intelligence/schemas.py src/backtester/intelligence/schemas.py
cp market_intelligence_v5_1_evidence_overlay/src/backtester/intelligence/evidence_graph.py src/backtester/intelligence/evidence_graph.py
cp market_intelligence_v5_1_evidence_overlay/src/backtester/intelligence/claim_extractor.py src/backtester/intelligence/claim_extractor.py
cp market_intelligence_v5_1_evidence_overlay/src/backtester/intelligence/evidence_scorer.py src/backtester/intelligence/evidence_scorer.py
cp market_intelligence_v5_1_evidence_overlay/src/backtester/intelligence/intelligence_engine.py src/backtester/intelligence/intelligence_engine.py
cp market_intelligence_v5_1_evidence_overlay/src/backtester/intelligence/source_loader.py src/backtester/intelligence/source_loader.py
cp market_intelligence_v5_1_evidence_overlay/scripts/inspect_evidence_graph.py scripts/inspect_evidence_graph.py
cp market_intelligence_v5_1_evidence_overlay/docs/market_intelligence_v5_1_evidence_graph.md docs/market_intelligence_v5_1_evidence_graph.md
python -m compileall -q src/backtester/intelligence scripts/inspect_evidence_graph.py
```

```bash
python scripts/inspect_evidence_graph.py \
  --query PLTR \
  --input data/intelligence/raw/pltr_sample_news.jsonl \
  --events-json outputs/intelligence/evidence_events.json \
  --claims-csv outputs/intelligence/evidence_claims.csv
```

Run the normal engine as before:

```bash
python scripts/run_market_intelligence.py \
  --query PLTR \
  --input data/intelligence/raw/pltr_sample_news.jsonl \
  --print-json
```

The report JSON now includes event metadata on evidence claims, and the feature CSV includes duplicate-aware evidence graph columns.

## Interpretation

- `raw_claim_count`: all extracted claims before clustering.
- `orthogonal_event_count`: event clusters after duplicate collapse.
- `duplicate_claim_count`: raw claims minus event clusters.
- `avg_event_trust`: source-aware event trust after confirmations and penalties.
- `avg_source_diversity`: how independent the event sourcing looks.
- `contradiction_event_count`: event clusters with opposing evidence nearby.

The intent is to let repeated coverage improve confidence only when it appears independently supported, while preventing syndicated or recycled headlines from linearly increasing signal strength.
