# Market Intelligence v1.8

v1.8 begins the shift from keyword sentiment to contextual event extraction.

## What changes

Instead of only producing a sentiment score, the system now extracts `MarketEvent` objects:

- `event_type`
- `scope`
- `direction`
- `magnitude`
- `confidence`
- `novelty`
- `persistence`
- `affected_entities`
- `source_reliability`
- `cluster_id`

## Optional NLP models

The extractor can use FinBERT through `transformers` when installed:

```text
--sentiment-backend finbert
```

It can use sentence-transformers clustering when installed:

```text
--cluster-backend sentence-transformers
```

If those libraries are missing, use:

```text
--sentiment-backend heuristic --cluster-backend heuristic
```

## Run

```bash
python -m scripts.extract_contextual_events \
  --queries PLTR QQQ MARKET \
  --input data/intelligence/raw/live_sources_yfinance.jsonl \
  --sentiment-backend auto \
  --cluster-backend auto
```

## Training boundary

The next training system must be walk-forward:

1. Use only news/events/prices known before week `t`.
2. Predict feature weights for week `t+1`.
3. Reveal next-week outcomes after the week ends.
4. Update/calibrate weights.

Never train using future news or future returns for the same decision date.
