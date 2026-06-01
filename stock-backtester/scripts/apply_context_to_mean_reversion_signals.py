# scripts/apply_context_to_mean_reversion_signals.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply market context weights to mean reversion signals."
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals.parquet",
        help="Raw mean reversion signal parquet file.",
    )
    parser.add_argument(
        "--context",
        default="outputs/context/market_context.parquet",
        help="Market context parquet file.",
    )
    parser.add_argument(
        "--out",
        default="outputs/signals/mean_reversion_signals_context_adjusted.parquet",
        help="Output adjusted signal parquet file.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="Rows to print.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    signal_path = Path(args.signals)
    context_path = Path(args.context)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not signal_path.exists():
        raise FileNotFoundError(f"Signal file not found: {signal_path}")

    if not context_path.exists():
        raise FileNotFoundError(f"Context file not found: {context_path}")

    signals = pd.read_parquet(signal_path)
    context = pd.read_parquet(context_path)

    if signals.empty:
        raise RuntimeError("Signal file is empty.")

    if context.empty:
        raise RuntimeError("Context file is empty.")

    signals["date"] = pd.to_datetime(signals["date"])
    context["date"] = pd.to_datetime(context["date"])

    context_cols = [
        "date",
        "realized_vol",
        "realized_vol_z",
        "return_entropy",
        "entropy_z",
        "volatility_state",
        "entropy_state",
        "volatility_weight",
        "entropy_weight",
        "context_weight",
    ]

    missing = [col for col in context_cols if col not in context.columns]
    if missing:
        raise ValueError(f"Missing context columns: {missing}")

    adjusted = signals.merge(
        context.loc[:, context_cols],
        on="date",
        how="left",
    )

    adjusted["context_weight"] = adjusted["context_weight"].fillna(0.75)
    adjusted["volatility_weight"] = adjusted["volatility_weight"].fillna(0.75)
    adjusted["entropy_weight"] = adjusted["entropy_weight"].fillna(0.75)
    adjusted["volatility_state"] = adjusted["volatility_state"].fillna("unknown")
    adjusted["entropy_state"] = adjusted["entropy_state"].fillna("unknown")

    adjusted["adjusted_confidence"] = (
        adjusted["confidence"] * adjusted["context_weight"]
    ).clip(lower=0.0, upper=1.0)

    adjusted["confidence_delta"] = (
        adjusted["adjusted_confidence"] - adjusted["confidence"]
    )

    adjusted = adjusted.sort_values(
        ["date", "horizon", "adjusted_confidence"],
        ascending=[True, True, False],
    )

    adjusted.to_parquet(out_path, index=False)

    print(f"Saved {len(adjusted):,} rows to {out_path}")

    latest_date = adjusted["date"].max()
    latest = adjusted[adjusted["date"] == latest_date].copy()

    print()
    print("=" * 80)
    print(f"Latest adjusted signals: {latest_date.date()}")
    print("=" * 80)

    display_cols = [
        "date",
        "ticker",
        "horizon",
        "direction",
        "confidence",
        "adjusted_confidence",
        "confidence_delta",
        "context_weight",
        "volatility_state",
        "entropy_state",
        "peer_spread_z",
        "peer_spread",
        "top_k_avg_corr",
        "peer_1",
        "peer_2",
        "peer_3",
        "peer_4",
        "peer_5",
    ]

    display_cols = [col for col in display_cols if col in adjusted.columns]

    latest_display = latest.sort_values(
        ["horizon", "adjusted_confidence"],
        ascending=[True, False],
    )

    print(latest_display.loc[:, display_cols].head(args.top).to_string(index=False))

    print()
    print("=" * 80)
    print("Average adjustment by volatility/entropy state")
    print("=" * 80)

    summary = (
        adjusted.groupby(["volatility_state", "entropy_state"])
        .agg(
            signal_count=("ticker", "count"),
            avg_confidence=("confidence", "mean"),
            avg_adjusted_confidence=("adjusted_confidence", "mean"),
            avg_context_weight=("context_weight", "mean"),
        )
        .reset_index()
        .sort_values("signal_count", ascending=False)
    )

    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
