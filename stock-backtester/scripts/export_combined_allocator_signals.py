# scripts/export_combined_allocator_signals.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export combined allocator table as a signal parquet compatible with Rust export."
    )

    parser.add_argument(
        "--combined-state",
        default="outputs/allocator/combined_market_signal_state.parquet",
        help="Combined market signal state table.",
    )
    parser.add_argument(
        "--out",
        default="outputs/signals/mean_reversion_signals_combined_allocator.parquet",
        help="Output signal parquet.",
    )
    parser.add_argument(
        "--score-col",
        default="final_signal_score",
        help="Column to use as adjusted_confidence.",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="Optional minimum final score filter.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = pd.read_parquet(args.combined_state).copy()

    required = {
        "date",
        "ticker",
        "direction",
        "confidence",
        "peer_spread_z",
        args.score_col,
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Combined state missing required columns: {sorted(missing)}"
        )

    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["direction"] = df["direction"].astype(str).str.lower().str.strip()

    df = df[df[args.score_col].notna()].copy()
    df = df[df[args.score_col].astype(float).ge(args.min_score)].copy()

    # Preserve original context-adjusted confidence before replacing adjusted_confidence.
    if "adjusted_confidence" in df.columns:
        df["pre_combined_allocator_adjusted_confidence"] = df["adjusted_confidence"].astype(float)
    else:
        df["pre_combined_allocator_adjusted_confidence"] = df["confidence"].astype(float)

    df["combined_allocator_score"] = df[args.score_col].astype(float)

    # Downstream Rust export uses adjusted_confidence.
    df["adjusted_confidence"] = df["combined_allocator_score"]

    # Keep confidence sane.
    df["confidence"] = df["confidence"].astype(float)

    preferred = [
        "date",
        "ticker",
        "engine",
        "window",
        "horizon",
        "direction",
        "raw_score",
        "normalized_score",
        "confidence",
        "adjusted_confidence",
        "combined_allocator_score",
        "pre_combined_allocator_adjusted_confidence",
        "stock_return",
        "peer_basket_return",
        "peer_spread",
        "peer_spread_z",
        "top_k_avg_corr",
        "peer_1",
        "peer_2",
        "peer_3",
        "peer_4",
        "peer_5",
        "market_context_weight",
        "market_volatility_state",
        "market_entropy_state",
        "market_volatility_weight",
        "market_entropy_weight",
        "market_realized_vol_z",
        "market_entropy_z",
        "market_compression_score",
        "compression_state",
        "compression_percentile",
        "fragmentation_percentile",
        "deformation_weight",
        "fabric_regime_group",
        "fabric_edge_mode",
        "ticker_stress_sensitivity",
        "ticker_stress_sensitivity_weight",
        "final_signal_score",
        "allocator_rank",
        "signal_state_label",
    ]

    existing = [c for c in preferred if c in df.columns]
    remaining = [c for c in df.columns if c not in existing]
    df = df[existing + remaining]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)

    print(f"Saved combined allocator signals: {len(df):,} rows -> {out}")
    print()
    print("Latest preview:")
    latest_date = df["date"].max()
    latest = (
        df[df["date"].eq(latest_date)]
        .sort_values("adjusted_confidence", ascending=False)
        .head(30)
    )
    print(latest[[
        "date",
        "ticker",
        "direction",
        "horizon",
        "confidence",
        "pre_combined_allocator_adjusted_confidence",
        "adjusted_confidence",
        "compression_state",
        "deformation_weight",
        "ticker_stress_sensitivity",
        "allocator_rank",
    ]].to_string(index=False))

    print()
    print("Score summary:")
    print(df["adjusted_confidence"].describe().to_string())

    print()
    print("Rows by compression_state:")
    if "compression_state" in df.columns:
        print(df["compression_state"].value_counts().to_string())


if __name__ == "__main__":
    main()
