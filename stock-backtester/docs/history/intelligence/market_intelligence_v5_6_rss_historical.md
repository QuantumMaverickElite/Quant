# Market Intelligence v5.6 — Historical RSS Collectors

This slice adds lightweight RSS providers to the historical news source pipeline without treating them as trusted ML-training feeds by default.

## Added providers

- `rss_yahoo` -> `rss_yahoo_finance`
  - Ticker-scoped Yahoo Finance RSS headlines.
  - Saved as canonical ticker rows.
  - `source_kind=news`.
  - Allowed for live scoring/backtesting/storage.
  - Blocked from ML training until source review.

- `rss_google` -> `rss_google_news`
  - Google News RSS search results.
  - Supports `--expand-entity-search`, so `PLTR` can search `PLTR` and `"Palantir Technologies"` while writing `query=PLTR`.
  - `source_kind=news_discovery`.
  - Requires confirmation and is blocked from ML training by default.

Both providers honor `--max-http-requests`, retries, sleeps, and provider policy. RSS rows include provider-policy metadata and preserve the actual search phrase in `raw.entity_search_query` when relevant.

## No-network preview

```bash
python scripts/fetch_historical_news_sources.py \
  --providers rss_google \
  --queries PLTR \
  --start 2026-06-24 \
  --end 2026-06-25 \
  --out /tmp/rss_entity_preview.jsonl \
  --offline \
  --expand-entity-search \
  --entity-master data/intelligence/entity_master.csv \
  --max-search-aliases 2
```

## Tiny live smoke

```bash
python scripts/fetch_historical_news_sources.py \
  --providers rss_yahoo rss_google \
  --queries PLTR \
  --start 2026-06-24 \
  --end 2026-06-25 \
  --out data/intelligence/historical/raw/rss_entity_search_smoke.jsonl \
  --expand-entity-search \
  --entity-master data/intelligence/entity_master.csv \
  --max-search-aliases 2 \
  --max-http-requests 3 \
  --max-retries 0
```

## Inspect

```bash
python -c "import json; from collections import Counter; p='data/intelligence/historical/raw/rss_entity_search_smoke.jsonl'; rows=[json.loads(x) for x in open(p) if x.strip()]; print('rows',len(rows)); print('providers',Counter(r.get('provider') for r in rows)); print('kinds',Counter(r.get('source_kind') for r in rows)); print([(r.get('query'), r.get('provider'), r.get('relevance_score'), r.get('raw',{}).get('entity_search_query'), r.get('title')) for r in rows[:10]])"
```

## Policy stance

RSS is useful for broader coverage, but it is not clean enough to train on by default. Yahoo RSS is treated as a medium-quality media feed. Google News RSS is discovery-only because search aggregation can be noisy. The feature builder will separate these through the existing `market_news`, `discovery_news`, `ml_allowed`, and `ml_blocked` policy-aware columns.
