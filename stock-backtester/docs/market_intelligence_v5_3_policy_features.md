# Market Intelligence v5.3 - Policy-Aware Historical News Features

This overlay turns provider policy metadata into point-in-time ML features.

## What Changed

- `src/backtester/intelligence/historical_news_feature_builder.py`
  - Preserves all existing news/analyst feature columns.
  - Adds provider policy parsing from either top-level `provider_policy` or `raw.provider_policy`.
  - Adds quality-weighted sentiment and source-quality counts over each rolling window.

- `scripts/build_historical_news_features.py`
  - Shows the new policy-aware feature columns in the preview.

## New Feature Families

For each window such as `7d`, `30d`, and `90d`:

- `news_policy_weight_sum_{window}d`
- `news_provider_quality_mean_{window}d`
- `news_sentiment_quality_weighted_{window}d`
- `ml_allowed_news_count_{window}d`
- `ml_blocked_news_count_{window}d`
- `ml_allowed_news_share_{window}d`
- `ml_allowed_news_sentiment_weighted_{window}d`
- `official_source_count_{window}d`
- `official_confirmation_recent_{window}d`
- `official_source_relevance_sum_{window}d`
- `high_quality_news_count_{window}d`
- `low_quality_news_count_{window}d`
- `requires_confirmation_count_{window}d`
- `unconfirmed_discovery_count_{window}d`
- `confirmed_discovery_count_{window}d`

Latest-record fields also now include:

- `news_latest_provider_quality_score`
- `news_latest_provider_quality_tier`
- `news_latest_is_official_source`
- `news_latest_allowed_for_ml_training`

## Apply

```bash
cp market_intelligence_v5_3_policy_features_overlay/src/backtester/intelligence/historical_news_feature_builder.py src/backtester/intelligence/historical_news_feature_builder.py
cp market_intelligence_v5_3_policy_features_overlay/scripts/build_historical_news_features.py scripts/build_historical_news_features.py
cp market_intelligence_v5_3_policy_features_overlay/docs/market_intelligence_v5_3_policy_features.md docs/market_intelligence_v5_3_policy_features.md
python -m compileall -q src/backtester/intelligence/historical_news_feature_builder.py scripts/build_historical_news_features.py
```

## Why This Matters

The model can now distinguish:

- noisy discovery-only coverage from high-quality market news,
- official SEC/company confirmation from ordinary media reports,
- ML-allowed sources from sources that should be excluded from training,
- low-trust unconfirmed discoveries from discoveries confirmed by official sources.

This keeps noisy sources useful as weak context without letting them poison the training target.
