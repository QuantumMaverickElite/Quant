# Market Intelligence v2.7

This patch adds semantic event taxonomy classification.

## Why

FinBERT only classifies sentiment. It can say a sentence is bullish or bearish,
but it does not know whether the event is about rates, valuation, earnings,
guidance, legal risk, price action, or company fundamentals.

v2.7 separates the problem:

- FinBERT: bullish / bearish / neutral / mixed
- Semantic event classifier: event type and market scope
- Sentence-transformers: event clustering

## New classifier

`semantic_event_classifier.py` embeds each sentence and compares it against label
definitions/examples for:

- price action
- rates
- inflation
- earnings
- guidance
- valuation
- liquidity
- legal/regulatory
- geopolitical
- sector rotation
- commodity
- company fundamentals
- analyst rating
- M&A
- general news

It also classifies scope:

- ticker
- peer group
- sector
- index
- macro
- political
- commodity
- unknown

## New flags

Use semantic taxonomy:

`--event-classifier semantic`

Keep old fallback:

`--event-classifier heuristic`

Recommended for small GPUs:

`--sentiment-backend finbert --event-classifier semantic --cluster-backend sentence-transformers --nlp-device cuda --event-classifier-device cpu --embedding-device cpu`

## Audit columns

Events now include:

- `event_classifier`
- `event_type_confidence`
- `scope_confidence`

These make it easier to inspect whether bad features came from sentiment or
taxonomy classification.
