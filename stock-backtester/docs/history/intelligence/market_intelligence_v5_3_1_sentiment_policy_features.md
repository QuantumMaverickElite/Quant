# Market Intelligence v5.3.1 - Scored News Sentiment Fix

This small overlay fixes policy-aware historical news features so already-scored news JSONL files contribute sentiment.

## Fix

`historical_news_feature_builder.source_sentiment()` now reads:

- `raw.model_sentiment_score`
- top-level `model_sentiment_score`
- Alpha Vantage sentiment fallback
- Finnhub recommendation-pressure fallback

This prevents scored files such as `news_eval_2025_2026_merged_full_scored.jsonl` from producing all-NaN `news_sentiment_*` columns.

## Apply

```bash
cp market_intelligence_v5_3_1_sentiment_policy_features_overlay/src/backtester/intelligence/historical_news_feature_builder.py src/backtester/intelligence/historical_news_feature_builder.py
cp market_intelligence_v5_3_1_sentiment_policy_features_overlay/docs/market_intelligence_v5_3_1_sentiment_policy_features.md docs/market_intelligence_v5_3_1_sentiment_policy_features.md
python -m compileall -q src/backtester/intelligence/historical_news_feature_builder.py scripts/build_historical_news_features.py
```
