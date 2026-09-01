from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.historical_news_collector import (
    HttpRequestBudget,
    entity_search_terms,
    fetch_alpha_vantage_news,
    fetch_finnhub_company_news,
    fetch_finnhub_recommendations,
    fetch_massive_ticker_news,
    fetch_newsapi_everything,
    fetch_polygon_ticker_news,
    fetch_google_news_rss,
    fetch_yahoo_finance_rss,
    parse_ymd,
    read_queries_file,
    write_news_records,
)
from backtester.intelligence.historical_source_collector import dedupe_records
from backtester.intelligence.provider_policy import annotate_record_policy, provider_allowed_for_usage, provider_min_interval


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch point-in-time historical news and analyst sources.")
    parser.add_argument("--providers", nargs="+", required=True, choices=[
        "alpha_vantage",
        "finnhub_news",
        "finnhub_recommendations",
        "massive_news",
        "newsapi",
        "polygon_news",
        "rss_yahoo",
        "rss_google",
    ])
    parser.add_argument("--queries", nargs="+")
    parser.add_argument("--queries-file", type=Path)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--massive-sleep-seconds", type=float, default=15.0)
    parser.add_argument("--max-retries", type=int, default=6)
    parser.add_argument("--backoff-seconds", type=float, default=30.0)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--usage", choices=["live_scoring", "backtesting", "ml_training", "storage"], default="backtesting")
    parser.add_argument("--ignore-provider-policy", action="store_true")
    parser.add_argument("--offline", action="store_true", help="Do not make network requests; useful while another API-heavy job is running.")
    parser.add_argument("--max-fetches", type=int, help="Maximum provider/query fetch attempts for this invocation. Does not count alias-expanded HTTP calls.")
    parser.add_argument("--max-http-requests", type=int, help="Maximum real HTTP attempts across providers, queries, aliases, pages, and retries.")
    parser.add_argument("--entity-master", type=Path, help="Entity master CSV path. Sets ENTITY_MASTER_PATH for this run.")
    parser.add_argument("--expand-entity-search", action="store_true", help="Use entity aliases for search-style providers while saving canonical ticker rows.")
    parser.add_argument("--max-search-aliases", type=int, default=2, help="Maximum search terms per ticker when --expand-entity-search is enabled.")
    parser.add_argument("--min-fetch-relevance", type=float, help="Minimum relevance score for RSS fetch outputs. Defaults to provider policy threshold; set 0 to keep all RSS rows.")
    parser.add_argument("--query-offset", type=int, default=0)
    parser.add_argument("--max-queries", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--mark-empty-complete", action="store_true")
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--alpha-vantage-key", default=os.environ.get("ALPHA_VANTAGE_API_KEY"))
    parser.add_argument("--finnhub-key", default=os.environ.get("FINNHUB_API_KEY"))
    parser.add_argument("--newsapi-key", default=os.environ.get("NEWSAPI_KEY"))
    parser.add_argument("--polygon-key", default=os.environ.get("POLYGON_API_KEY"))
    parser.add_argument("--massive-key", default=os.environ.get("MASSIVE_API_KEY"))
    return parser.parse_args()


def collect_queries(args: argparse.Namespace) -> list[str]:
    queries: list[str] = []
    if args.queries:
        queries.extend(args.queries)
    if args.queries_file:
        queries.extend(read_queries_file(args.queries_file))
    out: list[str] = []
    seen: set[str] = set()
    for query in queries:
        value = str(query).strip().upper()
        if value and value not in seen:
            out.append(value)
            seen.add(value)
    if not out:
        raise SystemExit("Provide --queries or --queries-file.")
    if args.query_offset:
        out = out[int(args.query_offset) :]
    if args.max_queries is not None:
        out = out[: int(args.max_queries)]
    return out


def record_to_dict(record: object) -> dict:
    if isinstance(record, dict):
        return annotate_record_policy(record)
    if hasattr(record, "to_dict"):
        return annotate_record_policy(record.to_dict())
    raise TypeError(f"Unsupported record type: {type(record)!r}")


def record_key(row: dict) -> str:
    provider_id = str(row.get("provider_article_id") or "")
    if provider_id:
        return f"{row.get('provider')}:{provider_id}"
    return "|".join(str(row.get(k) or "") for k in ("query", "url", "title", "published_at"))


def read_jsonl_dicts(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl_dicts(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    deduped: list[dict] = []
    for row in rows:
        key = record_key(row)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    with path.open("w", encoding="utf-8") as f:
        for row in deduped:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    rows[:] = deduped


def read_completed_state(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    completed: set[tuple[str, str]] = set()
    with path.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "complete":
                completed.add((str(row.get("provider") or ""), str(row.get("query") or "")))
    return completed


def append_state(path: Path, *, provider: str, query: str, status: str, records: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["provider", "query", "status", "records"])
        if not exists:
            writer.writeheader()
        writer.writerow({"provider": provider, "query": query, "status": status, "records": records})


def fetch_provider_query(provider: str, query: str, args: argparse.Namespace, start, end, request_budget: HttpRequestBudget | None = None):
    policy_sleep = provider_min_interval(provider)
    common = {
        "queries": [query],
        "sleep_seconds": max(args.sleep_seconds, policy_sleep),
        "max_retries": args.max_retries,
        "backoff_seconds": args.backoff_seconds,
        "timeout_seconds": args.timeout_seconds,
        "request_budget": request_budget,
    }
    if provider == "alpha_vantage":
        if not args.alpha_vantage_key:
            raise SystemExit("alpha_vantage requires --alpha-vantage-key or ALPHA_VANTAGE_API_KEY.")
        return fetch_alpha_vantage_news(
            start=start,
            end=end,
            api_key=args.alpha_vantage_key,
            limit=args.limit,
            **{**common, "sleep_seconds": max(args.sleep_seconds, policy_sleep, 12.0)},
        )
    if provider == "finnhub_news":
        if not args.finnhub_key:
            raise SystemExit("finnhub_news requires --finnhub-key or FINNHUB_API_KEY.")
        return fetch_finnhub_company_news(start=start, end=end, api_key=args.finnhub_key, limit=args.limit, **common)
    if provider == "finnhub_recommendations":
        if not args.finnhub_key:
            raise SystemExit("finnhub_recommendations requires --finnhub-key or FINNHUB_API_KEY.")
        return fetch_finnhub_recommendations(api_key=args.finnhub_key, **common)
    if provider == "newsapi":
        if not args.newsapi_key:
            raise SystemExit("newsapi requires --newsapi-key or NEWSAPI_KEY.")
        return fetch_newsapi_everything(
            start=start,
            end=end,
            api_key=args.newsapi_key,
            limit=args.limit,
            expand_entity_search=args.expand_entity_search,
            max_search_aliases=args.max_search_aliases,
            **common,
        )
    if provider == "massive_news":
        if not args.massive_key:
            raise SystemExit("massive_news requires --massive-key or MASSIVE_API_KEY.")
        return fetch_massive_ticker_news(
            start=start,
            end=end,
            api_key=args.massive_key,
            limit=args.limit,
            **{**common, "sleep_seconds": max(args.sleep_seconds, policy_sleep, args.massive_sleep_seconds)},
        )
    if provider == "polygon_news":
        if not args.polygon_key:
            raise SystemExit("polygon_news requires --polygon-key or POLYGON_API_KEY.")
        return fetch_polygon_ticker_news(start=start, end=end, api_key=args.polygon_key, limit=args.limit, **common)
    if provider == "rss_yahoo":
        return fetch_yahoo_finance_rss(
            start=start,
            end=end,
            limit=args.limit,
            min_relevance_score=args.min_fetch_relevance,
            **common,
        )
    if provider == "rss_google":
        return fetch_google_news_rss(
            start=start,
            end=end,
            limit=args.limit,
            expand_entity_search=args.expand_entity_search,
            max_search_aliases=args.max_search_aliases,
            min_relevance_score=args.min_fetch_relevance,
            **common,
        )
    raise SystemExit(f"Unsupported provider: {provider}")


def main() -> None:
    args = parse_args()
    if args.entity_master:
        os.environ["ENTITY_MASTER_PATH"] = str(args.entity_master)
    queries = collect_queries(args)
    start = parse_ymd(args.start)
    end = parse_ymd(args.end)
    state_file = args.state_file or args.out.with_suffix(args.out.suffix + ".state.csv")
    records = read_jsonl_dicts(args.out) if args.resume else []
    completed = read_completed_state(state_file) if args.resume else set()
    fetch_count = 0
    request_budget = HttpRequestBudget(args.max_http_requests) if args.max_http_requests is not None else None

    if args.offline:
        print("Offline mode enabled; no provider requests will be made.")
        print(f"Existing records: {len(records)}")
        if args.expand_entity_search:
            for query in queries[:20]:
                terms = entity_search_terms(query, max_terms=args.max_search_aliases)
                print(f"entity_search_terms {query}: {terms}")
        print(f"Saved: {args.out}")
        print(f"State: {state_file}")
        return

    if args.expand_entity_search:
        print(f"Entity search expansion enabled; max_search_aliases={args.max_search_aliases}")
        estimated = len(queries) * max(1, int(args.max_search_aliases))
        print(f"Estimated search-style provider requests per search-style provider: up to {estimated}")
        if args.max_http_requests is not None:
            print(f"HTTP request cap enabled: max_http_requests={args.max_http_requests}")
        for query in queries[:20]:
            terms = entity_search_terms(query, max_terms=args.max_search_aliases)
            print(f"entity_search_terms {query}: {terms}")

    stop_fetching = False
    for provider in args.providers:
        if stop_fetching:
            break
        if not args.ignore_provider_policy and not provider_allowed_for_usage(provider, args.usage):
            print(f"{provider}: skipped by provider policy for usage={args.usage}")
            continue
        for query in queries:
            if request_budget is not None and request_budget.exhausted:
                print(f"Reached --max-http-requests={args.max_http_requests}; stopping before {provider} {query}.")
                stop_fetching = True
                break
            if args.max_fetches is not None and fetch_count >= args.max_fetches:
                print(f"Reached --max-fetches={args.max_fetches}; stopping before {provider} {query}.")
                stop_fetching = True
                break
            pair = (provider, query)
            if pair in completed:
                print(f"{provider} {query}: skipped completed")
                continue
            print(f"{provider} fetch query={query}")
            batch = fetch_provider_query(provider, query, args, start, end, request_budget=request_budget)
            fetch_count += 1
            batch_dicts = [record_to_dict(record) for record in batch]
            print(f"{provider} {query}: {len(batch_dicts)} records")
            records.extend(batch_dicts)
            write_jsonl_dicts(records, args.out)
            if batch_dicts or args.mark_empty_complete:
                append_state(state_file, provider=provider, query=query, status="complete", records=len(batch_dicts))
                completed.add(pair)
            else:
                append_state(state_file, provider=provider, query=query, status="empty_retryable", records=0)
            if request_budget is not None and request_budget.exhausted:
                print(f"Reached --max-http-requests={args.max_http_requests}; stopping after {provider} {query}.")
                stop_fetching = True
                break

    if request_budget is not None:
        print(f"HTTP requests attempted: {request_budget.attempted}/{request_budget.max_requests}; skipped_after_cap={request_budget.skipped}")
    print(f"Providers: {', '.join(args.providers)}")
    print(f"Queries: {', '.join(queries)}")
    print(f"Date range: {args.start} to {args.end}")
    print(f"Records: {len(records)}")
    print(f"Saved: {args.out}")
    print(f"State: {state_file}")


if __name__ == "__main__":
    main()
