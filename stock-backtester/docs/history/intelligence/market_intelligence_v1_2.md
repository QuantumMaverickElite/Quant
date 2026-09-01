# Market Intelligence v1.2

v1.2 adds batch analysis.

## Batch CLI

```bash
python -m scripts.run_market_intelligence_batch \
  --queries PLTR QQQ MARKET \
  --input data/intelligence/raw/sample_market_news.jsonl \
  --price-features-csv data/intelligence/features/sample_price_risk_features.csv
```

or:

```bash
python -m scripts.run_market_intelligence_batch \
  --query-file data/intelligence/raw/sample_queries.txt \
  --input data/intelligence/raw/sample_market_news.jsonl \
  --price-features-csv data/intelligence/features/sample_price_risk_features.csv
```

## Outputs

Each batch run gets a UTC run id:

```text
outputs/intelligence/<run_id>/<QUERY>_report.json
```

Two append-only CSVs are updated:

```text
outputs/intelligence/intelligence_features.csv
outputs/intelligence/intelligence_batch_summary.csv
```

## Optional Price Feature CSV

```csv
query,peer_divergence,volume_shock,trend_damage
PLTR,0.15,0.20,0.10
QQQ,0.05,0.10,0.08
MARKET,0.00,0.05,0.05
```

These values should eventually come from the existing price and market-fabric pipelines.
