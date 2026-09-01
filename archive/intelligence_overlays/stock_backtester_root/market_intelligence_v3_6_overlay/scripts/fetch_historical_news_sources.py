from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.historical_news_collector import (
    fetch_alpha_vantage_news,
    fetch_finnhub_company_news,
    fetch_finnhub_recommendations,
    fetch_newsapi_everything,
    fetch_polygon_ticker_news,
    parse_ymd,
    read_queries_file,
    write_news_records,
)
from backtester.intelligence.historical_source_collector import dedupe_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch point-in-time historical news and analyst sources.")
    parser.add_argument("--providers", nargs="+", required=True, choices=[
        "alpha_vantage",
        "finnhub_news",
        "finnhub_recommendations",
        "newsapi",
        "polygon_news",
    ])
    parser.add_argument("--queries", nargs="+")
    parser.add_argument("--queries-file", type=Path)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--alpha-vantage-key", default=os.environ.get("ALPHA_VANTAGE_API_KEY"))
    parser.add_argument("--finnhub-key", default=os.environ.get("FINNHUB_API_KEY"))
    parser.add_argument("--newsapi-key", default=os.environ.get("NEWSAPI_KEY"))
    parser.add_argument("--polygon-key", default=os.environ.get("POLYGON_API_KEY"))
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
    return out


def main() -> None:
    args = parse_args()
    queries = collect_queries(args)
    start = parse_ymd(args.start)
    end = parse_ymd(args.end)
    records = []

    for provider in args.providers:
        if provider == "alpha_vantage":
            if not args.alpha_vantage_key:
                raise SystemExit("alpha_vantage requires --alpha-vantage-key or ALPHA_VANTAGE_API_KEY.")
            batch = fetch_alpha_vantage_news(
                queries=queries,
                start=start,
                end=end,
                api_key=args.alpha_vantage_key,
                limit=args.limit,
                sleep_seconds=max(args.sleep_seconds, 12.0),
            )
        elif provider == "finnhub_news":
            if not args.finnhub_key:
                raise SystemExit("finnhub_news requires --finnhub-key or FINNHUB_API_KEY.")
            batch = fetch_finnhub_company_news(
                queries=queries,
                start=start,
                end=end,
                api_key=args.finnhub_key,
                limit=args.limit,
                sleep_seconds=args.sleep_seconds,
            )
        elif provider == "finnhub_recommendations":
            if not args.finnhub_key:
                raise SystemExit("finnhub_recommendations requires --finnhub-key or FINNHUB_API_KEY.")
            batch = fetch_finnhub_recommendations(
                queries=queries,
                api_key=args.finnhub_key,
                sleep_seconds=args.sleep_seconds,
            )
        elif provider == "newsapi":
            if not args.newsapi_key:
                raise SystemExit("newsapi requires --newsapi-key or NEWSAPI_KEY.")
            batch = fetch_newsapi_everything(
                queries=queries,
                start=start,
                end=end,
                api_key=args.newsapi_key,
                limit=args.limit,
                sleep_seconds=args.sleep_seconds,
            )
        elif provider == "polygon_news":
            if not args.polygon_key:
                raise SystemExit("polygon_news requires --polygon-key or POLYGON_API_KEY.")
            batch = fetch_polygon_ticker_news(
                queries=queries,
                start=start,
                end=end,
                api_key=args.polygon_key,
                limit=args.limit,
                sleep_seconds=args.sleep_seconds,
            )
        else:
            raise SystemExit(f"Unsupported provider: {provider}")

        print(f"{provider}: {len(batch)} records")
        records.extend(batch)

    records = dedupe_records(records)
    write_news_records(records, args.out)
    print(f"Providers: {', '.join(args.providers)}")
    print(f"Queries: {', '.join(queries)}")
    print(f"Date range: {args.start} to {args.end}")
    print(f"Records: {len(records)}")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
