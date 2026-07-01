#!/usr/bin/env python3
from __future__ import annotations

import argparse

from backtester.intelligence.event_day_impact_dataset import (
    build_event_day_impact_dataset,
    write_event_day_impact_dataset,
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--events",
        default="outputs/intelligence/event_impact_dataset.parquet",
        help="Event-level impact dataset.",
    )
    p.add_argument(
        "--out",
        default="outputs/intelligence/event_day_impact_dataset.parquet",
        help="Ticker-day aggregated impact dataset.",
    )
    p.add_argument("--horizon", type=int, default=5)
    p.add_argument("--benchmark", default="SPY")
    args = p.parse_args()

    df = build_event_day_impact_dataset(
        event_impact_path=args.events,
        horizon=args.horizon,
        benchmark_ticker=args.benchmark,
    )
    write_event_day_impact_dataset(df, args.out)

    print(f"rows: {len(df)}")
    print(f"tickers: {df['ticker'].nunique()}")
    print(f"target horizon: {args.horizon}d")
    print()
    print("target_forward_alpha summary:")
    print(df["target_forward_alpha"].describe())
    print()
    print("event_count summary:")
    print(df["event_count"].describe())
    print()
    print("rows by ticker:")
    print(df.groupby("ticker").size().sort_values(ascending=False).to_string())
    print()
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
