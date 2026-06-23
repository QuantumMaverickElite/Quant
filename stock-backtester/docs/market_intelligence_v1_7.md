# Market Intelligence v1.7

v1.7 adds readable reporting and allocator-ready exports.

## Brief

```bash
python -m scripts.summarize_market_intelligence \
  --signals outputs/signals/mean_reversion_latest_with_intelligence.parquet \
  --top-n 20
```

Outputs:

```text
outputs/intelligence/latest_market_intelligence_brief.txt
outputs/intelligence/latest_market_intelligence_summary.csv
```

## Allocator-ready signals

```bash
python -m scripts.build_allocator_intelligence_signals \
  --signals outputs/signals/mean_reversion_latest_with_intelligence.parquet \
  --out outputs/signals/mean_reversion_allocator_intelligence.parquet
```

This creates:

- `allocator_confidence_pre_intelligence`
- `allocator_confidence_intelligence_adjusted`
- `allocator_confidence_delta`
- `intelligence_position_scale`
- `allocator_intelligence_enabled`

## Important boundary

Current live intelligence should be used for live/latest candidate selection. It should not be used to claim historical backtest improvements unless the news/evidence layer is rebuilt point-in-time for each historical date.
