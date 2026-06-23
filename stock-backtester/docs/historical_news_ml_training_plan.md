# Historical News ML Training Plan

## Can We Scrape Past News?

Yes, but loose scraping is not enough for valid ML training.

The useful dataset must be point-in-time:

- article `published_at` timestamp
- source identity and reliability
- ticker/entity mapping
- raw text or stable extracted event record
- the exact signal date the model would have known the article
- rolling windows such as 1d, 3d, 7d, 30d
- no article or revision from after the signal date

If this rule is violated, the model will learn from future information and the backtest will look better than reality.

## Recommended Source Tiers

### Tier 1: Public, Reliable, Point-in-Time

- SEC EDGAR filings and company facts
- FRED macro time series
- Treasury/Fed/BLS/BEA macro releases
- GDELT global news/event metadata and article discovery

These are good for broad context, macro events, filings, and public event history.

### Tier 2: Market News APIs

Use if they provide historical article search with publish timestamps and terms that allow storage/analysis.

Examples to evaluate:

- NewsAPI or similar article-search APIs
- Marketaux / Finnhub / Polygon / Benzinga / Tiingo / Alpha Vantage news endpoints
- vendor archives if affordable

For each provider, verify:

- historical depth
- ticker/entity tagging quality
- whether full text is available or only title/summary
- storage rights
- rate limits
- cost

### Tier 3: Raw Website Scraping

This should be last resort.

Problems:

- terms-of-service risk
- robots/rate-limit issues
- inconsistent article pages
- paywalls
- incomplete timestamps
- survivorship bias
- revised articles

If used, scrape only allowed sources, store URL/title/timestamp/text, and keep a source audit log.

## Historical Feature Design

For each signal date and ticker, build features from news known before that date:

- `news_1d_sentiment`
- `news_7d_sentiment`
- `news_30d_sentiment`
- `event_count_1d`
- `event_count_7d`
- `macro_event_pressure_7d`
- `ticker_event_pressure_7d`
- `sector_event_pressure_30d`
- `rates_event_pressure_30d`
- `valuation_event_pressure_30d`
- `regime_break_news_pressure`
- `positive_opportunity_pressure`
- `negative_idiosyncratic_pressure`
- `source_reliability_weighted_sentiment`
- `novelty_weighted_event_pressure`

Then join these to:

- baseline allocator confidence
- volatility regime features
- entropy features
- correlation/peer divergence features
- mean-reversion signal features
- forward returns and drawdowns

## Training Loop

1. Pick signal dates.
2. For each signal date, use only news published before that date.
3. Extract events and aggregate features.
4. Label outcomes over 5d, 10d, 20d.
5. Train bounded/ridge/logistic models.
6. Validate walk-forward by month or quarter.
7. Compare:
   - baseline strategy
   - heuristic NLP strategy
   - ML-calibrated NLP strategy
   - random portfolios
8. Promote ML weights only if they beat heuristic NLP out-of-sample.

## Current Decision

Do not replace the heuristic NLP allocator yet.

The immediate ML priority is data collection and point-in-time feature generation, not more model complexity.
