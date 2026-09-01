# Market Intelligence v5.6.1 — RSS Relevance Gate

This patch keeps the v5.6 RSS collectors, but filters low-relevance RSS rows at fetch time.

Why:

- Yahoo Finance ticker RSS can include broad market headlines inside a ticker feed.
- In the PLTR smoke, rows such as broad market/Dow/Nasdaq headlines were saved with `relevance_score=0.0`.
- These should not enter downstream source files by default.

Behavior:

- `rss_yahoo` defaults to the provider policy minimum relevance threshold, currently `0.45`.
- `rss_google` defaults to the provider policy minimum relevance threshold, currently `0.75`.
- Filtered rows are counted and printed, e.g. `rss_yahoo: skipped 2 low-relevance rows below 0.45`.
- To keep every RSS row for raw inspection, pass `--min-fetch-relevance 0`.
- To make RSS stricter, pass a larger value such as `--min-fetch-relevance 0.70`.

Recommended smoke:

```bash
python scripts/fetch_historical_news_sources.py \
  --providers rss_yahoo rss_google \
  --queries PLTR \
  --start 2026-06-24 \
  --end 2026-06-25 \
  --out data/intelligence/historical/raw/rss_entity_search_smoke_filtered.jsonl \
  --expand-entity-search \
  --entity-master data/intelligence/entity_master.csv \
  --max-search-aliases 2 \
  --max-http-requests 3 \
  --max-retries 0
```

Optional raw inspection mode:

```bash
python scripts/fetch_historical_news_sources.py \
  --providers rss_yahoo rss_google \
  --queries PLTR \
  --start 2026-06-24 \
  --end 2026-06-25 \
  --out /tmp/rss_raw_keep_all.jsonl \
  --expand-entity-search \
  --entity-master data/intelligence/entity_master.csv \
  --max-search-aliases 2 \
  --max-http-requests 3 \
  --max-retries 0 \
  --min-fetch-relevance 0
```
