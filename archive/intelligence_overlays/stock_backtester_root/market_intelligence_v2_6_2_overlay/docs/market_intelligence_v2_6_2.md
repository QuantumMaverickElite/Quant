# Market Intelligence v2.6.2

This patch improves NLP event taxonomy quality after the first FinBERT smoke test.

## Fixes

- Avoids substring false positives, such as matching `war` inside `software`.
- Adds a `price_action` event type.
- Narrows price-action matching so generic phrases like `yields rose` remain rates/macro events.
- Adds a small alias map so `Palantir` can scope to `PLTR`.
- Adds `price_action_event_pressure` to event features and allocator opportunity/risk scoring.

## Why this matters

FinBERT improved sentiment interpretation, but the surrounding event taxonomy was
still too keyword-heavy. This patch keeps NLP sentiment while making event type
and scope cleaner before we rebuild event features.
