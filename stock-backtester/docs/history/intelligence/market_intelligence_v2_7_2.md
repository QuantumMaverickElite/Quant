# Market Intelligence v2.7.2

This patch adds document-context classification.

## Why

Sentence-only classification fails on fragments such as:

- `Revenue is growing 84.7% year over year`
- `That requires roughly $1,300`
- `How low it could go`

Those fragments need article title and neighboring sentence context.

## What changed

- Semantic classifier input is now:
  - article title
  - previous sentence
  - current sentence
  - next sentence
- Stored event text remains the compact current sentence.
- Events now include `classification_context` for auditing.
- Query matching now uses entity aliases such as `Palantir` -> `PLTR`.
- Fallback event type/scope still come from the current sentence to avoid context leakage.
- QQQ/SPY-style index queries ground to `index`, not `ticker`.

## Recommended smoke test

Use:

`--sentiment-backend finbert --event-classifier semantic --cluster-backend sentence-transformers --nlp-device cuda --event-classifier-device cpu --embedding-device cpu --show-context`

The `--show-context` flag helps debug whether the classifier had enough evidence.
