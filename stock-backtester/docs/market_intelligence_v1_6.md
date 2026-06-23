# Market Intelligence v1.6

v1.6 makes the intelligence layer usable from the rest of the quant project.

## One-command live run

Manual list:

```bash
python -m scripts.run_market_intelligence_live \
  --queries PLTR QQQ MARKET \
  --sources yfinance \
  --download-prices
```

Candidate sweep from a signal table:

```bash
python -m scripts.run_market_intelligence_live \
  --candidates outputs/signals/mean_reversion_signals_market_common_stock_only_v3_context_adjusted.parquet \
  --top-n 50 \
  --sources yfinance \
  --download-prices
```

Useful overrides:

```bash
--ticker-col ticker
--rank-col adjusted_confidence
--benchmark QQQ
--peer-map data/intelligence/features/sample_peer_map.csv
```

## Join intelligence back into signals

```bash
python -m scripts.apply_intelligence_to_signals \
  --signals outputs/signals/mean_reversion_signals_market_common_stock_only_v3_context_adjusted.parquet \
  --features outputs/intelligence/intelligence_features.csv \
  --out outputs/signals/mean_reversion_signals_with_intelligence.parquet
```

This appends:

- `regime_break_score`
- `price_action_risk`
- `news_pressure`
- `macro_pressure`
- `sector_pressure`
- `idiosyncratic_pressure`
- `intelligence_action_label`
- `intelligence_confidence_multiplier`
- `<confidence_col>_pre_intelligence`
- `<confidence_col>_intelligence_adjusted`

## Philosophy

Do not scan the whole market yet. Sweep top 20-100 candidates from the existing quant engine, then use intelligence to decide whether the candidate deserves full confidence, caution, or a scale-in ban.
