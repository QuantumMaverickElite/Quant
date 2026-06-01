# scripts/inspect_correlation_features.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect generated correlation feature output."
    )

    parser.add_argument(
        "--features",
        default="outputs/correlation/features.parquet",
        help="Path to correlation features parquet file.",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=120,
        help="Rolling correlation window to inspect.",
    )
    parser.add_argument(
        "--latest-only",
        action="store_true",
        help="Only inspect the latest available date.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of rows to show per section.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    path = Path(args.features)

    if not path.exists():
        raise FileNotFoundError(f"Feature file not found: {path}")

    features = pd.read_parquet(path)

    if features.empty:
        raise RuntimeError("Feature file is empty.")

    frame = features[features["window"] == args.window].copy()

    if frame.empty:
        available = sorted(features["window"].unique().tolist())
        raise RuntimeError(
            f"No rows found for window={args.window}. Available windows: {available}"
        )

    if args.latest_only:
        latest_date = frame["date"].max()
        frame = frame[frame["date"] == latest_date].copy()
    else:
        latest_date = frame["date"].max()

    print()
    print("=" * 80)
    print("Correlation Feature Inspection")
    print("=" * 80)
    print(f"Feature file: {path}")
    print(f"Rows: {len(frame):,}")
    print(f"Window: {args.window}")
    print(f"Date range: {frame['date'].min().date()} → {frame['date'].max().date()}")
    print(f"Latest date: {latest_date.date()}")

    latest = frame[frame["date"] == latest_date].copy()

    print()
    print("=" * 80)
    print(f"Latest snapshot: {latest_date.date()}")
    print("=" * 80)

    print()
    print("Highest market correlation:")
    print(
        latest.sort_values("market_corr", ascending=False)
        .loc[
            :,
            ["ticker", "market_corr", "sector_corr", "industry_corr", "top_k_avg_corr"],
        ]
        .head(args.top)
        .to_string(index=False)
    )

    print()
    print("Lowest market correlation:")
    print(
        latest.sort_values("market_corr", ascending=True)
        .loc[
            :,
            ["ticker", "market_corr", "sector_corr", "industry_corr", "top_k_avg_corr"],
        ]
        .head(args.top)
        .to_string(index=False)
    )

    print()
    print("Highest top-k peer correlation:")
    print(
        latest.sort_values("top_k_avg_corr", ascending=False)
        .loc[
            :,
            [
                "ticker",
                "top_k_avg_corr",
                "peer_1",
                "peer_1_corr",
                "peer_2",
                "peer_2_corr",
                "peer_3",
                "peer_3_corr",
            ],
        ]
        .head(args.top)
        .to_string(index=False)
    )

    print()
    print("Lowest top-k peer correlation:")
    print(
        latest.sort_values("top_k_avg_corr", ascending=True)
        .loc[
            :,
            [
                "ticker",
                "top_k_avg_corr",
                "peer_1",
                "peer_1_corr",
                "peer_2",
                "peer_2_corr",
                "peer_3",
                "peer_3_corr",
            ],
        ]
        .head(args.top)
        .to_string(index=False)
    )
    if args.latest_only:
        print()
        print("Skipping time-series summaries because --latest-only was used.")
        return

    print()
    print("=" * 80)
    print("Time-series summary by ticker")
    print("=" * 80)

    summary = (
        frame.groupby("ticker")
        .agg(
            market_corr_mean=("market_corr", "mean"),
            market_corr_std=("market_corr", "std"),
            sector_corr_mean=("sector_corr", "mean"),
            industry_corr_mean=("industry_corr", "mean"),
            top_k_avg_corr_mean=("top_k_avg_corr", "mean"),
            top_k_avg_corr_std=("top_k_avg_corr", "std"),
        )
        .reset_index()
    )

    print()
    print("Most consistently market-correlated:")
    print(
        summary.sort_values("market_corr_mean", ascending=False)
        .head(args.top)
        .to_string(index=False)
    )

    print()
    print("Most unstable top-k peer correlation:")
    print(
        summary.sort_values("top_k_avg_corr_std", ascending=False)
        .head(args.top)
        .to_string(index=False)
    )

    peer_cols = [
        col
        for col in frame.columns
        if col.startswith("peer_") and not col.endswith("_corr")
    ]

    peer_counts = (
        frame.melt(
            id_vars=["date", "ticker"],
            value_vars=peer_cols,
            value_name="peer",
        )
        .dropna(subset=["peer"])
        .groupby(["ticker", "peer"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    print()
    print("=" * 80)
    print("Most persistent peer relationships")
    print("=" * 80)
    print(peer_counts.head(args.top * 2).to_string(index=False))


if __name__ == "__main__":
    main()
