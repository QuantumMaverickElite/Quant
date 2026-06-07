# scripts/build_market_fabric_allocator_overlay.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build market-fabric overlay table from pseudo-allocator features."
    )

    parser.add_argument(
        "--allocator",
        default="outputs/allocator/pseudo_allocator_feature_table.parquet",
        help="Pseudo-allocator feature table.",
    )
    parser.add_argument(
        "--out",
        default="outputs/market_fabric/allocator_overlay.parquet",
        help="Full allocator overlay parquet.",
    )
    parser.add_argument(
        "--latest-out",
        default="outputs/market_fabric/allocator_overlay_latest.csv",
        help="Latest-date allocator overlay CSV.",
    )
    parser.add_argument(
        "--summary-out",
        default="outputs/market_fabric/allocator_overlay_summary.csv",
        help="Date-level allocator overlay summary CSV.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top allocator picks to flag per date.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = pd.read_parquet(args.allocator).copy()

    required = {
        "date",
        "ticker",
        "final_signal_score",
        "compression_state",
        "market_compression_score",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Allocator table missing required columns: {sorted(missing)}"
        )

    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()

    # Collapse to one node per date/ticker.
    # Keep the strongest allocator score for each ticker on each date.
    sort_cols = ["date", "ticker", "final_signal_score"]
    df = df.sort_values(sort_cols, ascending=[True, True, False])

    node = (
        df.groupby(["date", "ticker"], as_index=False)
        .head(1)
        .copy()
    )

    node["allocator_rank"] = (
        node.groupby("date")["final_signal_score"]
        .rank(method="first", ascending=False)
    )

    node["node_score_percentile"] = (
        node.groupby("date")["final_signal_score"]
        .rank(method="average", pct=True)
    )

    node["is_top_allocator_pick"] = node["allocator_rank"].le(args.top_n)

    # A clean visual intensity field for graph/fabric use.
    # Higher score -> brighter/larger/stronger node.
    node["fabric_node_intensity"] = node["node_score_percentile"]

    # Useful for visual styling.
    node["fabric_regime_group"] = node["compression_state"].map(
        {
            "BROAD_COMPRESSION": "compression",
            "MODERATE_COMPRESSION": "compression",
            "STABLE": "stable",
            "BROAD_FRAGMENTATION": "fragmentation",
            "MODERATE_FRAGMENTATION": "fragmentation",
        }
    ).fillna("unknown")

    preferred_cols = [
        "date",
        "ticker",
        "direction",
        "engine",
        "window",
        "horizon",
        "confidence",
        "adjusted_confidence",
        "pre_allocator_confidence",
        "context_weight",
        "volatility_state",
        "entropy_state",
        "market_compression_score",
        "compression_state",
        "fabric_regime_group",
        "compression_percentile",
        "fragmentation_percentile",
        "deformation_weight",
        "deformation_adjusted_confidence",
        "ticker_stress_sensitivity",
        "ticker_stress_sensitivity_weight",
        "final_signal_score",
        "allocator_rank",
        "node_score_percentile",
        "fabric_node_intensity",
        "is_top_allocator_pick",
        "peer_spread_z",
        "top_k_avg_corr",
        "realized_vol_z",
        "entropy_z",
    ]

    existing_preferred = [col for col in preferred_cols if col in node.columns]
    remaining = [col for col in node.columns if col not in existing_preferred]
    node = node[existing_preferred + remaining]

    summary = (
        node.groupby(["date", "compression_state"], dropna=False)
        .agg(
            node_count=("ticker", "size"),
            top_pick_count=("is_top_allocator_pick", "sum"),
            avg_final_signal_score=("final_signal_score", "mean"),
            max_final_signal_score=("final_signal_score", "max"),
            avg_market_compression_score=("market_compression_score", "mean"),
            avg_ticker_stress_sensitivity=("ticker_stress_sensitivity", "mean"),
        )
        .reset_index()
        .sort_values(["date", "max_final_signal_score"], ascending=[True, False])
    )

    out_path = Path(args.out)
    latest_path = Path(args.latest_out)
    summary_path = Path(args.summary_out)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    node.to_parquet(out_path, index=False)
    summary.to_csv(summary_path, index=False)

    latest_date = node["date"].max()
    latest = node[node["date"].eq(latest_date)].sort_values(
        "final_signal_score",
        ascending=False,
    )

    latest.to_csv(latest_path, index=False)

    print(f"Saved fabric allocator overlay: {len(node):,} rows -> {out_path}")
    print(f"Saved latest overlay: {len(latest):,} rows -> {latest_path}")
    print(f"Saved overlay summary: {len(summary):,} rows -> {summary_path}")
    print()
    print("Latest date:", latest_date.date())
    print()
    print(
        latest[
            [
                "date",
                "ticker",
                "compression_state",
                "fabric_regime_group",
                "final_signal_score",
                "allocator_rank",
                "node_score_percentile",
                "is_top_allocator_pick",
                "ticker_stress_sensitivity",
            ]
        ].head(30).to_string(index=False)
    )


if __name__ == "__main__":
    main()
