# scripts/build_market_fabric_visual_overlay.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a clean visual overlay table for market fabric rendering."
    )

    parser.add_argument(
        "--overlay",
        default="outputs/market_fabric/allocator_overlay.parquet",
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

    df = pd.read_parquet(args.overlay).copy()

    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()

    required_cols = [
        "date",
        "ticker",
        "final_signal_score",
        "allocator_rank",
        "compression_state",
        "fabric_regime_group",
        "market_compression_score",
        "compression_percentile",
        "fragmentation_percentile",
        "deformation_weight",
        "ticker_stress_sensitivity",
        "node_score_percentile",
        "fabric_node_intensity",
        "peer_spread_z",
        "top_k_avg_corr",
    ]

    keep_cols = [col for col in required_cols if col in df.columns]
    visual = df[keep_cols].copy()

    visual["is_top_1_allocator_pick"] = visual["allocator_rank"].le(1)
    visual["is_top_3_allocator_pick"] = visual["allocator_rank"].le(3)
    visual["is_top_5_allocator_pick"] = visual["allocator_rank"].le(5)

    visual["fabric_edge_mode"] = visual["fabric_regime_group"].map(
        {
            "compression": "tighten_edges",
            "stable": "normal_edges",
            "fragmentation": "loosen_edges",
        }
    ).fillna("normal_edges")

    visual["fabric_node_role"] = "neutral"
    visual.loc[visual["is_top_5_allocator_pick"], "fabric_node_role"] = "allocator_candidate"
    visual.loc[visual["is_top_3_allocator_pick"], "fabric_node_role"] = "high_priority_candidate"
    visual.loc[visual["is_top_1_allocator_pick"], "fabric_node_role"] = "top_candidate"

    # Size/intensity helpers for later visuals.
    visual["node_size_score"] = visual["node_score_percentile"].clip(0.05, 1.0)
    visual["node_alpha_score"] = visual["fabric_node_intensity"].clip(0.10, 1.0)

    visual = visual.sort_values(["date", "allocator_rank", "ticker"]).reset_index(drop=True)

    out_path = Path(args.out)
    latest_path = Path(args.latest_out)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.parent.mkdir(parents=True, exist_ok=True)

    visual.to_parquet(out_path, index=False)

    latest_date = visual["date"].max()
    latest = visual[visual["date"].eq(latest_date)].copy()
    latest.to_csv(latest_path, index=False)

    print(f"Saved visual overlay: {len(visual):,} rows -> {out_path}")
    print(f"Saved latest visual overlay: {len(latest):,} rows -> {latest_path}")
    print()
    print("Latest date:", latest_date.date())
    print()
    print(latest.to_string(index=False))


if __name__ == "__main__":
    main()
