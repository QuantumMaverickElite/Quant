# Phase 25 overlay preservation manifest

This is the live preservation decision for the ignored
`market_intelligence_*_overlay` directories observed on 2026-08-31. The new
[Phase 25 per-file manifest](PHASE25_OVERLAY_PRESERVATION.csv) records all 289
source paths, sizes, SHA-256 hashes, current tracked counterpart candidates,
relationships, and decisions. The Phase 0 [lineage manifest](overlay_lineage.csv)
remains historical evidence, but its old canonical-destination fields predate
later documentation and research moves.

## Inventory and integrity

| Scope | Overlays | Source/document files | Status |
| --- | ---: | ---: | --- |
| Repository root | 10 | 27 | ignored/local |
| `stock-backtester/` root | 56 | 262 | ignored/local |
| Total | 66 | 289 | not recoverable from Git |

Python cache files were excluded. Hashing the sorted list of each file's
SHA-256 plus path produced this aggregate SHA-256:

```text
7225c8d7e31925e09ee00737d3e2becde81b09425a9e3d2cfb3ce74182278c47
```

A live comparison against tracked current files, including basename matches
for files moved during the reorganization, classified 132 files as identical,
156 as different, and one as having no tracked counterpart. `DIFFERENT` does
not prove a file is the preferred version; it proves Git cannot reconstruct the
overlay bytes from the current counterpart.

The canonical-missing file is:

```text
stock-backtester/market_intelligence_v2_6_2_overlay/docs/market_intelligence_v2_6_2.md
SHA-256 37b9dc082c673ca814792f2fb17eb71faf9f3173d47ec6581464f0ff91fbaf58
```

## Decisions

All overlays are `KEEP_IN_PLACE` for this phase. Eight are mechanically
`SAFE_TO_ARCHIVE` because every inspected file matched a tracked counterpart,
but no archival destination was authorized. The remaining 58 are
`UNIQUE_CONTENT_REQUIRES_PRESERVATION` because at least one file differed or
had no tracked counterpart. No overlay was moved, deleted, or rewritten.

Root overlays are summarized below. The project-root overlays are enumerated
afterward so every observed bundle has an explicit decision.

| Root overlay | Files | Live comparison | Phase 25 decision |
| --- | ---: | --- | --- |
| `market_intelligence_v3_0_overlay` | 3 | 1 identical, 2 different | preserve in place |
| `market_intelligence_v4_4_overlay` | 2 | 2 different | preserve in place |
| `market_intelligence_v4_5_overlay` | 2 | 2 different | preserve in place |
| `market_intelligence_v4_6_overlay` | 3 | 3 different | preserve in place |
| `market_intelligence_v4_7_overlay` | 2 | 2 different | preserve in place |
| `market_intelligence_v4_8_overlay` | 2 | 2 different | preserve in place |
| `market_intelligence_v4_9_overlay` | 3 | 2 identical, 1 different | preserve in place |
| `market_intelligence_v5_0_overlay` | 5 | 4 identical, 1 different | preserve in place |
| `market_intelligence_v5_0_1_overlay` | 2 | all identical | safe candidate; kept in place |
| `market_intelligence_v5_0_2_overlay` | 3 | 2 identical, 1 different | preserve in place |

The 56 project-root overlays, all kept in place, are:

```text
market_intelligence_v2_10_overlay
market_intelligence_v2_2_overlay
market_intelligence_v2_3_overlay
market_intelligence_v2_4_overlay
market_intelligence_v2_5_overlay
market_intelligence_v2_6_overlay
market_intelligence_v2_6_1_overlay
market_intelligence_v2_6_2_overlay
market_intelligence_v2_7_overlay
market_intelligence_v2_7_1_overlay
market_intelligence_v2_7_2_overlay
market_intelligence_v2_7_3_overlay
market_intelligence_v2_7_4_overlay
market_intelligence_v2_7_5_overlay
market_intelligence_v2_8_overlay
market_intelligence_v2_8_1_overlay
market_intelligence_v2_9_overlay
market_intelligence_v3_0_1_overlay
market_intelligence_v3_0_2_overlay
market_intelligence_v3_1_overlay
market_intelligence_v3_2_overlay
market_intelligence_v3_3_overlay
market_intelligence_v3_3_1_overlay
market_intelligence_v3_4_overlay
market_intelligence_v3_4_1_overlay
market_intelligence_v3_5_overlay
market_intelligence_v3_6_overlay
market_intelligence_v3_7_overlay
market_intelligence_v3_8_overlay
market_intelligence_v3_9_overlay
market_intelligence_v3_9_1_overlay
market_intelligence_v3_9_2_overlay
market_intelligence_v4_0_overlay
market_intelligence_v4_1_overlay
market_intelligence_v4_2_overlay
market_intelligence_v4_3_overlay
market_intelligence_v4_4_overlay
market_intelligence_v4_5_overlay
market_intelligence_v4_7_overlay
market_intelligence_v5_1_evidence_clean_overlay
market_intelligence_v5_2_1_sec_policy_overlay
market_intelligence_v5_2_policy_clean_overlay
market_intelligence_v5_3_1_sentiment_policy_features_clean_overlay
market_intelligence_v5_3_2_source_kind_features_clean_overlay
market_intelligence_v5_3_policy_features_clean_overlay
market_intelligence_v5_4_1_entity_false_positive_overlay
market_intelligence_v5_4_entity_master_overlay
market_intelligence_v5_5_1_request_budget_overlay
market_intelligence_v5_5_entity_search_overlay
market_intelligence_v5_6_1_rss_relevance_overlay
market_intelligence_v5_6_2_text_relevance_overlay
market_intelligence_v5_6_3_rss_title_gate_overlay
market_intelligence_v5_6_rss_historical_overlay
market_intelligence_v5_7_1_training_launcher_fix_overlay
market_intelligence_v5_7_2_training_launcher_prices_overlay
market_intelligence_v5_7_long_training_launcher_overlay
```

## Reconstruction and archival rule

The original layout is reconstructable only from preserved overlay bytes plus
their recorded paths; Git alone is insufficient. Before any later archival
move, select a durable destination, copy rather than delete, verify all 289 file
hashes and the aggregate hash at the destination, and only then decide whether
to remove the source directories. The `SAFE_TO_ARCHIVE` label is not deletion
authorization.

## User decision required

Choose a durable overlay destination: a tracked archive, an external artifact
store, or verified compact archives accompanied by tracked manifests.
