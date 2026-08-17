#!/usr/bin/env python3
from __future__ import annotations

import argparse

from backtester.intelligence.events.event_fact_table import (
    build_event_fact_table,
    write_event_fact_table,
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--news",
        default="outputs/worker_ingest/chromebook/cbworker_news_sources.parquet",
        help="Normalized worker news table.",
    )
    p.add_argument(
        "--universe",
        default="data/reference/ticker_universe_sec.parquet",
        help="Ticker/company metadata table.",
    )
    p.add_argument(
        "--out",
        default="outputs/intelligence/event_fact_table.parquet",
        help="Output event fact table.",
    )
    args = p.parse_args()

    df = build_event_fact_table(news_path=args.news, universe_path=args.universe)
    write_event_fact_table(df, args.out)

    print(f"rows: {len(df)}")
    print(f"tickers: {df['ticker'].nunique()}")
    print(f"providers: {', '.join(sorted(df['provider'].dropna().astype(str).unique()))}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
