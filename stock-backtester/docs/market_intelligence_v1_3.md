# Market Intelligence v1.3

v1.3 adds automatic price-risk feature generation.

The output CSV feeds directly into the v1.2 batch runner:

```text
query,peer_divergence,volume_shock,trend_damage
```

## Quick Download Run

```bash
python -m scripts.build_intelligence_price_features \
  --queries PLTR QQQ MARKET \
  --download \
  --benchmark QQQ \
  --peer-map data/intelligence/features/sample_peer_map.csv \
  --out data/intelligence/features/price_risk_features.csv
```

Then:

```bash
python -m scripts.run_market_intelligence_batch \
  --queries PLTR QQQ MARKET \
  --input data/intelligence/raw/sample_market_news.jsonl \
  --price-features-csv data/intelligence/features/price_risk_features.csv
```

## Local Price File Run

```bash
python -m scripts.build_intelligence_price_features \
  --queries PLTR QQQ MARKET \
  --prices path/to/prices.csv \
  --benchmark QQQ \
  --out data/intelligence/features/price_risk_features.csv
```

Supported local price shapes:

- long OHLCV: `date,ticker,close,volume`
- long adjusted: `date,ticker,adj_close,volume`
- wide close matrix: `date,PLTR,QQQ,SPY,...`

## Feature Meaning

- `peer_divergence`: risk that the query is underperforming its benchmark/peer basket.
- `volume_shock`: risk from abnormal latest volume.
- `trend_damage`: risk from drawdown, moving-average deterioration, and recent negative momentum.

These are v1 approximations. Later they should be replaced or blended with the existing market-fabric, deformation, and allocator-context outputs.
