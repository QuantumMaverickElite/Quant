# Market Intelligence v1.6.1

Hotfix for date-aware integration.

## Why

The first integration joined current intelligence features onto every historical row for the same ticker. That is fine for a live candidate report, but wrong for a historical signal table.

## Changes

- Adds `--latest-date-only` to candidate sweeps.
- Adds `--latest-date-only` to signal integration.
- Historical rows are marked `not_evaluated_historical_row` and keep their original confidence.
- Only the newest signal date gets current intelligence labels and confidence adjustments.

## Live candidate sweep

```bash
python -m scripts.run_market_intelligence_live \
  --candidates outputs/signals/mean_reversion_signals_market_common_stock_only_v3_context_adjusted.parquet \
  --top-n 50 \
  --latest-date-only \
  --sources yfinance \
  --download-prices
```

## Date-aware join

```bash
python -m scripts.apply_intelligence_to_signals \
  --signals outputs/signals/mean_reversion_signals_market_common_stock_only_v3_context_adjusted.parquet \
  --features outputs/intelligence/intelligence_features.csv \
  --out outputs/signals/mean_reversion_latest_with_intelligence.parquet \
  --latest-date-only
```
