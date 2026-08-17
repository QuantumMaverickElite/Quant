#!/usr/bin/env python3
from __future__ import annotations

import argparse

from backtester.intelligence.events.event_outcome_labels import (
    label_event_outcomes,
    write_labeled_events,
)


def parse_horizons(raw: str) -> tuple[int, ...]:
    return tuple(int(x.strip()) for x in raw.split(",") if x.strip())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--events",
        default="outputs/intelligence/event_fact_table.parquet",
        help="Event fact table.",
    )
    p.add_argument(
        "--prices",
        default="outputs/worker_ingest/chromebook/cbworker_yahoo_chart_prices.parquet",
        help="Price table with ticker,date,close.",
    )
    p.add_argument(
        "--out",
        default="outputs/intelligence/event_outcome_labels.parquet",
        help="Output labeled event table.",
    )
    p.add_argument("--horizons", default="1,5,20")
    p.add_argument("--benchmark", default="SPY")
    args = p.parse_args()

    horizons = parse_horizons(args.horizons)

    df = label_event_outcomes(
        events_path=args.events,
        prices_path=args.prices,
        horizons=horizons,
        benchmark_ticker=args.benchmark,
    )
    write_labeled_events(df, args.out)

    label_cols = [c for c in df.columns if c.startswith("forward_return_")]

    print(f"rows: {len(df)}")
    print(f"tickers: {df['ticker'].nunique()}")
    for col in label_cols:
        print(f"{col}: non-null {df[col].notna().sum()}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
