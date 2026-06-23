from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.batch import read_query_file
from backtester.intelligence.source_fetcher import (
    DEFAULT_USER_AGENT,
    default_source_output_path,
    fetch_documents_for_queries,
    write_documents_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch live intelligence source snippets into the engine JSONL format."
    )
    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--queries", nargs="+", help="Tickers/topics, e.g. PLTR QQQ MARKET.")
    query_group.add_argument("--query-file", type=Path, help="One query per line.")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["all", "yfinance", "yahoo", "google", "sec"],
        default=["all"],
        help="Source families to fetch. Default: all.",
    )
    parser.add_argument("--max-items-per-source", type=int, default=8)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="HTTP User-Agent. Set SEC_USER_AGENT env var for a better default.",
    )
    return parser.parse_args()


def normalize_sources(values: list[str]) -> set[str]:
    sources = {value.lower() for value in values}
    if "all" in sources:
        return {"yfinance", "yahoo", "google", "sec"}
    return sources


def main() -> None:
    args = parse_args()
    queries = args.queries if args.queries is not None else read_query_file(args.query_file)
    queries = [query.strip().upper() for query in queries if query.strip()]
    if not queries:
        raise SystemExit("No queries provided.")

    out = args.out or default_source_output_path()
    docs = fetch_documents_for_queries(
        queries,
        sources=normalize_sources(args.sources),
        max_items_per_source=args.max_items_per_source,
        user_agent=args.user_agent,
    )
    write_documents_jsonl(docs, out)

    print(f"Saved sources: {out}")
    print(f"Documents: {len(docs)}")
    by_source: dict[str, int] = {}
    for doc in docs:
        by_source[doc.source] = by_source.get(doc.source, 0) + 1
    for source, count in sorted(by_source.items()):
        print(f"{source}: {count}")


if __name__ == "__main__":
    main()
