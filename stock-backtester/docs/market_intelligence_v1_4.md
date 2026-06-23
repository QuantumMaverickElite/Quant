# Market Intelligence v1.4

v1.4 adds live-ish source ingestion.

It fetches source snippets into the same JSONL format consumed by the intelligence engine.

## Sources

- `yahoo`: Yahoo Finance ticker RSS.
- `yfinance`: yfinance ticker news, useful because the project already uses yfinance for prices.
- `google`: Google News RSS search for ticker/topic market news.
- `sec`: SEC EDGAR company ticker map and recent submissions metadata.

The SEC endpoint is a trusted source for company filings metadata. It does not require an API key, but it does expect responsible request behavior and a useful User-Agent.

Set:

```bash
export SEC_USER_AGENT="stock-backtester/0.1 your_email@example.com"
```

## Fetch Sources

```bash
python -m scripts.fetch_intelligence_sources \
  --queries PLTR QQQ MARKET \
  --sources all \
  --max-items-per-source 8 \
  --out data/intelligence/raw/live_sources_pltr_qqq_market.jsonl
```

If RSS endpoints are blocked, try the source that is most likely to work in the current project environment:

```bash
python -m scripts.fetch_intelligence_sources \
  --queries PLTR QQQ \
  --sources yfinance \
  --out data/intelligence/raw/live_sources_yfinance.jsonl
```

## Full Flow

```bash
python -m scripts.fetch_intelligence_sources \
  --queries PLTR QQQ MARKET \
  --sources all \
  --out data/intelligence/raw/live_sources_pltr_qqq_market.jsonl

python -m scripts.build_intelligence_price_features \
  --queries PLTR QQQ MARKET \
  --download \
  --benchmark QQQ \
  --peer-map data/intelligence/features/sample_peer_map.csv \
  --out data/intelligence/features/price_risk_features.csv

python -m scripts.run_market_intelligence_batch \
  --queries PLTR QQQ MARKET \
  --input data/intelligence/raw/live_sources_pltr_qqq_market.jsonl \
  --price-features-csv data/intelligence/features/price_risk_features.csv
```

## Notes

This is still not institutional-grade news. It is the first real ingestion layer:

- RSS snippets are noisy and may be shallow.
- SEC metadata is trusted but does not yet extract full filing text.
- Paid or stronger feeds can later write the same JSONL schema.
