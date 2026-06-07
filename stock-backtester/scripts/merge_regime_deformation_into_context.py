# scripts/merge_regime_deformation_into_context.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge regime correlation deformation features into market context."
    )

    parser.add_argument(
        "--context",
        default="outputs/context/market_context.parquet",
    )
    parser.add_argument(
        "--deformation",
        default="outputs/correlation/regime_market_deformation.csv",
    )
    parser.add_argument(
        "--out",
        default="outputs/context/market_context_with_regime_deformation.parquet",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    context = pd.read_parquet(args.context)
    deformation = pd.read_csv(args.deformation)

    context["date"] = pd.to_datetime(context["date"])
    deformation["date"] = pd.to_datetime(deformation["date"])

    deformation_cols = [
        "date",
        "avg_corr",
        "avg_calm_baseline_corr",
        "avg_stress_baseline_corr",
        "market_compression_score",
        "stress_distance_score",
        "pairs_above_calm_baseline",
        "pairs_below_calm_baseline",
        "pair_count",
        "compression_state",
        "compression_percentile",
        "fragmentation_percentile",
    ]

    merged = context.merge(
        deformation[deformation_cols],
        on="date",
        how="left",
    )

    # The deformation engine is step-based, usually every 5 trading days.
    # Forward-fill so daily market context can consume the latest known structure state.
    fill_cols = [col for col in deformation_cols if col != "date"]
    merged[fill_cols] = merged[fill_cols].ffill()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    merged.to_parquet(out_path, index=False)

    print(f"Saved {len(merged):,} rows -> {out_path}")
    print("Columns:")
    print(list(merged.columns))
    print()
    print(merged.tail(30).to_string(index=False))


if __name__ == "__main__":
    main()
