# Market Intelligence v5.6.2 — Text-first relevance for search/RSS sources

This patch tightens relevance scoring for search-style feeds such as Yahoo Finance RSS, Google News RSS, and NewsAPI.

Problem fixed:

- Search/RSS records could receive high relevance because the ticker appeared in URL/query metadata instead of the human-visible title/body.
- That allowed broad or unrelated rows to pass fetch-time relevance gates.

Behavior now:

- RSS and NewsAPI relevance scores are based on title/body text only.
- URL matches are kept only in `raw.relevance_audit` for diagnostics.
- `raw.relevance_audit.url_only_entity_match=true` shows when a row had only URL evidence and was therefore not enough to pass the gate.
- Ticker-scoped structured providers such as Finnhub, Massive, Polygon, and Alpha Vantage keep their existing provider-specific behavior.

Recommended smoke:

```bash
python scripts/fetch_historical_news_sources.py \
  --providers rss_yahoo rss_google \
  --queries PLTR \
  --start 2026-06-24 \
  --end 2026-06-25 \
  --out data/intelligence/historical/raw/rss_entity_search_smoke_text_filtered.jsonl \
  --expand-entity-search \
  --entity-master data/intelligence/entity_master.csv \
  --max-search-aliases 2 \
  --max-http-requests 3 \
  --max-retries 0
```
