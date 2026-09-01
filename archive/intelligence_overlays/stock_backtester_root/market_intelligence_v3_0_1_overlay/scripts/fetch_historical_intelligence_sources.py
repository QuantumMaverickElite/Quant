from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.historical_source_collector import (
    fetch_gdelt_historical_sources,
    parse_ymd,
    read_queries_file,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch historical point-in-time intelligence sources.")
    parser.add_argument("--provider", choices=["gdelt"], default="gdelt")
    parser.add_argument("--queries", nargs="+")
    parser.add_argument("--queries-file", type=Path)
    parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end", required=True, help="End date in YYYY-MM-DD format.")
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--max-records-per-query-window", type=int, default=75)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--backoff-seconds", type=float, default=5.0)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/intelligence/historical/raw/gdelt_sources.jsonl"),
    )
    return parser.parse_args()


def resolve_queries(args: argparse.Namespace) -> list[str]:
    queries: list[str] = []
    if args.queries:
        queries.extend(args.queries)
    if args.queries_file:
        queries.extend(read_queries_file(args.queries_file))
    out: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = query.strip().upper()
        if normalized and normalized not in seen:
            out.append(normalized)
            seen.add(normalized)
    if not out:
        raise SystemExit("Provide --queries or --queries-file.")
    return out


def main() -> None:
    args = parse_args()
    queries = resolve_queries(args)
    start = parse_ymd(args.start)
    end = parse_ymd(args.end)

    if args.provider == "gdelt":
        records = fetch_gdelt_historical_sources(
            queries=queries,
            start=start,
            end=end,
            window_days=args.window_days,
            max_records_per_query_window=args.max_records_per_query_window,
            sleep_seconds=args.sleep_seconds,
            max_retries=args.max_retries,
            backoff_seconds=args.backoff_seconds,
        )
    else:
        raise SystemExit(f"Unsupported provider: {args.provider}")

    write_jsonl(records, args.out)
    print(f"Provider: {args.provider}")
    print(f"Queries: {', '.join(queries[:20])}{' ...' if len(queries) > 20 else ''}")
    print(f"Date range: {start} to {end}")
    print(f"Records: {len(records)}")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
