# scripts/build_market_fabric_visual_overlay_from_combined_state.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build market fabric visual overlay from combined market signal state."
    )

    parser.add_argument(
        "--combined-state",
        default="outputs/allocator/combined_market_signal_state.parquet",
    )
    parser.add_argument(
        "--out",
        default="outputs/market_fabric/allocator_visual_overlay.parquet",
    )
    parser.add_argument(
        "--latest-out",
        default="outputs/market_fabric/allocator_visual_overlay_latest.csv",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = pd.read_parquet(args.combined_state).copy()

    required = {
        "date",
        "ticker",
        "final_signal_score",
        "allocator_rank",
        "compression_state",
        "fabric_regime_group",
        "fabric_edge_mode",
        "market_compression_score",
        "compression_percentile",
        "fragmentation_percentile",
        "deformation_weight",
        "ticker_stress_sensitivity",
        "peer_spread_z",
        "top_k_avg_corr",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Combined state missing required columns: {sorted(missing)}")

    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()

    # One node per ticker/date: keep strongest final allocator score.
    df = df.sort_values(
        ["date", "ticker", "final_signal_score"],
        ascending=[True, True, False],
    )

    visual = (
        df.groupby(["date", "ticker"], as_index=False)
        .head(1)
        .copy()
    )

    visual["allocator_rank"] = (
        visual.groupby("date")["final_signal_score"]
        .rank(method="first", ascending=False)
    )

    visual["node_score_percentile"] = (
        visual.groupby("date")["final_signal_score"]
        .rank(method="average", pct=True)
    )

    visual["fabric_node_intensity"] = visual["node_score_percentile"]

    visual["is_top_1_allocator_pick"] = visual["allocator_rank"].le(1)
    visual["is_top_3_allocator_pick"] = visual["allocator_rank"].le(3)
    visual["is_top_5_allocator_pick"] = visual["allocator_rank"].le(5)

    visual["fabric_node_role"] = "neutral"
    visual.loc[visual["is_top_5_allocator_pick"], "fabric_node_role"] = "allocator_candidate"
    visual.loc[visual["is_top_3_allocator_pick"], "fabric_node_role"] = "high_priority_candidate"
    visual.loc[visual["is_top_1_allocator_pick"], "fabric_node_role"] = "top_candidate"

    visual["node_size_score"] = visual["node_score_percentile"].clip(0.05, 1.0)
    visual["node_alpha_score"] = visual["fabric_node_intensity"].clip(0.10, 1.0)

    keep = [
        "date",
        "ticker",
        "final_signal_score",
        "allocator_rank",
        "compression_state",
        "fabric_regime_group",
        "fabric_edge_mode",
        "fabric_node_role",
        "market_compression_score",
        "compression_percentile",
        "fragmentation_percentile",
        "deformation_weight",
        "ticker_stress_sensitivity",
        "node_score_percentile",
        "fabric_node_intensity",
        "node_size_score",
        "node_alpha_score",
        "is_top_1_allocator_pick",
        "is_top_3_allocator_pick",
        "is_top_5_allocator_pick",
        "peer_spread_z",
        "top_k_avg_corr",
    ]

    visual = visual[keep].sort_values(["date", "allocator_rank", "ticker"])

    out = Path(args.out)
    latest_out = Path(args.latest_out)

    out.parent.mkdir(parents=True, exist_ok=True)
    latest_out.parent.mkdir(parents=True, exist_ok=True)

    visual.to_parquet(out, index=False)

    latest_date = visual["date"].max()
    latest = visual[visual["date"].eq(latest_date)].copy()
    latest.to_csv(latest_out, index=False)

    print(f"Saved visual overlay: {len(visual):,} rows -> {out}")
    print(f"Saved latest visual overlay: {len(latest):,} rows -> {latest_out}")
    print()
    print("Latest date:", latest_date.date())
    print()
    print(latest.to_string(index=False))


if __name__ == "__main__":
    main()
