# Market Intelligence v2.7.3

This patch improves context handling after the v2.7.2 smoke test.

## What changed

- FinBERT sentiment now sees title + current sentence only.
- Semantic taxonomy still sees title + previous/current/next sentence.
- Adds `grounded_event_type`.
- Adds `raw_semantic_event_type` audit field.

## Why

Using neighboring sentences for sentiment caused leakage:

`commercial just jumped 133%...`

could become bearish because the next sentence said shares were down.

Now sentiment stays focused on the current claim, while taxonomy can still use
neighboring context to understand fragments.

## Guardrails

The event type guardrails fix cases like:

- revenue growth -> `earnings`
- Rule of 40 / commercial growth -> `earnings`
- trillion-club / $1,300 target speculation -> `valuation`
- M&A only when actual deal terms appear

The smoke script prints raw semantic type/scope when a guardrail corrected it.
