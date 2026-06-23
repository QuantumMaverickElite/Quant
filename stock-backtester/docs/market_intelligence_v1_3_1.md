# Market Intelligence v1.3.1

Hotfix for price-risk feature generation.

## Fixes

- Treats broad topics such as `MARKET`, `MACRO`, `FED`, and `RATES` as intelligence topics, not Yahoo tickers.
- Downloads only real ticker-like symbols plus benchmark and peer-map tickers.
- Handles empty/missing price rows without crashing.
- For non-price topics with peer-map entries, builds aggregate volume/trend risk from the mapped peers.

## Example

```bash
python -m scripts.build_intelligence_price_features \
  --queries PLTR QQQ MARKET \
  --download \
  --benchmark QQQ \
  --peer-map data/intelligence/features/sample_peer_map.csv \
  --out data/intelligence/features/price_risk_features.csv
```
