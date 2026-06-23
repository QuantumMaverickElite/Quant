# Market Intelligence v2.3

This patch improves positive-news handling for allocator integration.

## What changed

- Opportunity boosts now use cross-sectional ranks across the current evaluated
  candidate sweep.
- Event downside penalties can also use cross-sectional ranks.
- Ranks ignore historical rows and missing-intelligence rows.
- Existing regime gates still block boosts for caution/damaged setups.

## Why this exists

The contextual event feature builder intentionally produces conservative scores.
That is good for stability, but it made positive events too small to move the
allocator. v2.3 keeps absolute score limits, but also asks whether a candidate is
unusually positive compared with the rest of today's sweep.

## Interpretation

- `event_opportunity_score`: absolute positive evidence strength.
- `event_opportunity_rank`: percentile rank among evaluated candidates.
- `event_opportunity_multiplier`: bounded upside boost after regime gates.
- `event_downside_risk_score`: absolute negative evidence strength.
- `event_downside_risk_rank`: percentile rank among evaluated candidates.
- `event_downside_multiplier`: bounded downside haircut.
- `net_event_multiplier`: final event multiplier applied to allocator confidence.

This is still deterministic. It is a better bridge to the later ML calibration
step because the model can learn the bounded weights and thresholds rather than
starting from unscaled raw event scores.
