# Market Intelligence v5.5 Entity-Aware Search

v5.5 uses the entity master to expand search-style news collection without changing downstream ticker keys.

## Behavior

Ticker-scoped providers still query by ticker:

- Finnhub company news
- Finnhub recommendations
- Massive/Polygon ticker news
- Alpha Vantage ticker news sentiment

Search-style providers can now use entity aliases:

- NewsAPI Everything

When `--expand-entity-search` is enabled, NewsAPI requests use high-precision search terms like:

- `PLTR`
- `"Palantir Technologies"`

But saved records keep:

- `query=PLTR`
- `raw.entity_search_query="Palantir Technologies"`
- `raw.canonical_query=PLTR`

That means historical features, evidence graphs, and joins continue to use ticker keys while collection becomes company-aware.

## CLI

No-network preview:

`python scripts/fetch_historical_news_sources.py --providers newsapi --queries PLTR --start 2026-05-01 --end 2026-05-02 --out /tmp/entity_search_preview.jsonl --offline --expand-entity-search --entity-master data/intelligence/entity_master.csv`

Small live batch:

`python scripts/fetch_historical_news_sources.py --providers newsapi --queries PLTR --start 2026-05-01 --end 2026-05-02 --out data/intelligence/historical/raw/newsapi_entity_search_smoke.jsonl --expand-entity-search --entity-master data/intelligence/entity_master.csv --max-search-aliases 2 --max-fetches 1`

## Rate Limit Note

`--max-search-aliases 2` means up to two NewsAPI requests per ticker: the ticker and the best company-name phrase. Raise it only after small batches look clean.
