# Market Intelligence v2.2

This patch connects the richer contextual event/opportunity feature file back into
the allocator path and adds allocator diagnostics.

## What changed

- `build_allocator_intelligence_signals_v2.py` now accepts `--opportunity-features`.
- The allocator can merge `intelligence_features_opportunity_scored.csv` by ticker.
- Historical rows labeled `not_evaluated_historical_row` are protected from current
  event multipliers.
- `diagnose_allocator_intelligence.py` reports top pre/post candidates, event boosts,
  event penalties, and optional forward-return comparison.

## Why this matters

Before this patch, the allocator could reward positive sentiment already present in
the signal table, but it was not guaranteed to use the richer contextual event
columns produced by:

- `extract_contextual_events.py`
- `build_contextual_event_features.py`
- `score_event_opportunities.py`

Now those contextual features can be merged into the allocator-ready signal table.

## Main flow

1. Build event/opportunity-scored features.
2. Build allocator-ready signals with `--opportunity-features`.
3. Run diagnostics on the allocator output.

For true historical performance testing, use point-in-time historical intelligence
features. Do not apply one current news snapshot across historical rows.
