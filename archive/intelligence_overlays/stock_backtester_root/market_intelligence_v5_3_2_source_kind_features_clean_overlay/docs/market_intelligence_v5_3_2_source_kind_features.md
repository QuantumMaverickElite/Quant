# Market Intelligence v5.3.2 - Source-Kind Split Features

This overlay keeps all existing v5.3/v5.3.1 columns and adds source-kind splits so media/news, SEC filings, and discovery sources are not mixed together.

## New Feature Families

For each rolling window:

- `media_news_count_{window}d`
- `media_news_relevance_sum_{window}d`
- `media_news_sentiment_quality_weighted_{window}d`
- `market_news_count_{window}d`
- `market_news_relevance_sum_{window}d`
- `market_news_sentiment_quality_weighted_{window}d`
- `official_filing_count_{window}d`
- `official_filing_relevance_sum_{window}d`
- `discovery_news_count_{window}d`
- `discovery_news_relevance_sum_{window}d`
- `discovery_news_sentiment_quality_weighted_{window}d`

## Interpretation

- `media_news_*`: ordinary article/news sentiment sources.
- `market_news_*`: media/news after excluding discovery-only and official filing records.
- `official_filing_*`: SEC/company-official style records.
- `discovery_news_*`: sources that require confirmation, such as GDELT-style discovery feeds.

The old `news_count_*` columns remain for compatibility, but the new split columns should be preferred in model research.
