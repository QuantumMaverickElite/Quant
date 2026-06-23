# Market Intelligence v1.9

v1.9 turns contextual events into model-ready features.

## What it adds

For each query/ticker/topic:

- `contextual_event_risk`
- `macro_event_pressure`
- `sector_event_pressure`
- `index_event_pressure`
- `ticker_event_pressure`
- `political_event_pressure`
- `rates_event_pressure`
- `inflation_event_pressure`
- `valuation_event_pressure`
- `event_count`
- `event_cluster_count`
- `bearish_event_share`
- `bullish_event_share`
- `mean_event_novelty`

## Run

```bash
python -m scripts.build_contextual_event_features \
  --events outputs/intelligence/contextual_events.jsonl
```

## Merge with existing intelligence features

```bash
python -m scripts.build_contextual_event_features \
  --events outputs/intelligence/contextual_events.jsonl \
  --merge-intelligence-features outputs/intelligence/intelligence_features.csv \
  --merged-out outputs/intelligence/intelligence_features_with_events.csv
```

## Why this matters

This is the first point where broad macro and sector events become separate model inputs rather than being collapsed into a simple sentiment score.

The next step is walk-forward training:

1. Build event features for week `t`.
2. Predict next-week weights.
3. Reveal week `t+1` outcomes.
4. Update calibration.
