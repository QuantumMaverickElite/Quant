#!/usr/bin/env python3
from __future__ import annotations

import argparse

from backtester.intelligence.event_impact_dataset import (
    build_event_impact_dataset,
    write_event_impact_dataset,
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--labels",
        default="outputs/intelligence/event_outcome_labels.parquet",
        help="Event table with forward outcome labels.",
    )
    p.add_argument(
        "--out",
        default="outputs/intelligence/event_impact_dataset.parquet",
        help="Output ML-ready event impact dataset.",
    )
    p.add_argument("--horizon", type=int, default=5)
    args = p.parse_args()

    df = build_event_impact_dataset(
        labeled_events_path=args.labels,
        min_label_horizon=args.horizon,
    )
    write_event_impact_dataset(df, args.out)

    print(f"rows: {len(df)}")
    print(f"tickers: {df['ticker'].nunique()}")
    print(f"trainable rows: {df['is_trainable'].sum()}")
    print(f"target horizon: {args.horizon}d")
    print()
    print("target_forward_alpha summary:")
    print(df.loc[df["is_trainable"], "target_forward_alpha"].describe())
    print()
    print("event type counts:")
    cols = [c for c in df.columns if c.startswith("event_type_") and not c.endswith("_count")]
    for c in cols:
        print(f"{c}: {int(df[c].sum())}")
    print()
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
