# Phase 8: Intelligence Features Topology

The user-performed Phase 8 move groups three downstream historical research
transformations under one physical owner:

- `src/backtester/intelligence/features/historical_news_feature_builder.py`
- `src/backtester/intelligence/features/historical_news_sentiment.py`
- `src/backtester/intelligence/features/historical_panel_builder.py`

The family sits between source acquisition and learning/calibration. It is
distinct from the event schema/data layer in `intelligence/events/` and the
NLP/event-extraction runtime in `intelligence/llm/`; none of these paths is
allocator authority.

The user-facing commands remain stable:

- `scripts/build_historical_news_features.py`
- `scripts/build_historical_intelligence_panel_seed.py`
- `scripts/score_historical_news_sentiment.py`

Their imports now use `backtester.intelligence.features`. The six source and
provider modules remain at the intelligence root because remote worker bundles,
provider/network behavior, and literal output paths require a separate forensic
move before relocation.
