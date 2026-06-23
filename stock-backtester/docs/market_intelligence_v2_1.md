# Market Intelligence v2.1

v2.1 adds balanced opportunity and risk scoring.

## Why

Earlier versions mostly punished bad context. v2.1 can also reward positive context, but with conservative caps.

## New fields

- `event_opportunity_score`
- `event_downside_risk_score`
- `event_opportunity_multiplier_raw`
- `event_opportunity_multiplier`
- `event_downside_multiplier`
- `net_event_multiplier`
- `net_event_score`

## Bounds

By default:

- opportunity can boost up to `1.25x`
- event downside can haircut up to `0.55x`
- opportunity boost is gated off when regime break / price action damage is too high

## Commands

Score merged intelligence/event features:

```text
python -m scripts.score_event_opportunities --features outputs/intelligence/intelligence_features_with_events.csv --out outputs/intelligence/intelligence_features_opportunity_scored.csv
```

Build allocator-ready signals with opportunity/risk scoring:

```text
python -m scripts.build_allocator_intelligence_signals_v2 --signals outputs/signals/mean_reversion_latest_with_intelligence.parquet --out outputs/signals/mean_reversion_allocator_intelligence_v2.parquet
```
