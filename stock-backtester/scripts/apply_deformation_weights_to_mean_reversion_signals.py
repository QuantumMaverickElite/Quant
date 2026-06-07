# scripts/apply_deformation_weights_to_mean_reversion_signals.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

DEFAULT_WEIGHTS = {
    "BROAD_COMPRESSION": 1.25,
    "MODERATE_COMPRESSION": 1.10,
    "STABLE": 1.00,
    "BROAD_FRAGMENTATION": 0.75,
    "MODERATE_FRAGMENTATION": 0.50,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply regime-correlation deformation weights to mean-reversion signals."
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals_context_adjusted.parquet",
        help="Input context-adjusted mean-reversion signals.",
    )
    parser.add_argument(
        "--context",
        default="outputs/context/market_context_with_regime_deformation.parquet",
        help="Market context with deformation features.",
    )
    parser.add_argument(
        "--out",
        default="outputs/signals/mean_reversion_signals_deformation_weighted.parquet",
        help="Output deformation-weighted signal file.",
    )

    parser.add_argument("--broad-compression-weight", type=float, default=1.25)
    parser.add_argument("--moderate-compression-weight", type=float, default=1.10)
    parser.add_argument("--stable-weight", type=float, default=1.00)
    parser.add_argument("--broad-fragmentation-weight", type=float, default=0.75)
    parser.add_argument("--moderate-fragmentation-weight", type=float, default=0.50)

    return parser.parse_args()


def build_weight_map(args: argparse.Namespace) -> dict[str, float]:
    return {
        "BROAD_COMPRESSION": args.broad_compression_weight,
        "MODERATE_COMPRESSION": args.moderate_compression_weight,
        "STABLE": args.stable_weight,
        "BROAD_FRAGMENTATION": args.broad_fragmentation_weight,
        "MODERATE_FRAGMENTATION": args.moderate_fragmentation_weight,
    }


def main() -> None:
    args = parse_args()

    signals = pd.read_parquet(args.signals)
    context = pd.read_parquet(args.context)

    if "date" not in signals.columns:
        raise ValueError("Signals file must contain a date column.")

    if "date" not in context.columns:
        raise ValueError("Context file must contain a date column.")

    signals["date"] = pd.to_datetime(signals["date"])
    context["date"] = pd.to_datetime(context["date"])

    context_cols = [
        "date",
        "market_compression_score",
        "compression_state",
        "compression_percentile",
        "fragmentation_percentile",
    ]

    missing_context_cols = [col for col in context_cols if col not in context.columns]
    if missing_context_cols:
        raise ValueError(
            "Context file is missing columns: " + ", ".join(missing_context_cols)
        )

    merged = signals.merge(
        context[context_cols],
        on="date",
        how="left",
    )

    weight_map = build_weight_map(args)

    merged["compression_state"] = (
        merged["compression_state"].astype(str).str.upper().str.strip()
    )

    merged["deformation_weight"] = (
        merged["compression_state"].map(weight_map).fillna(1.0).astype(float)
    )

    # Preserve the old confidence before changing anything.
    if "adjusted_confidence" in merged.columns:
        base_col = "adjusted_confidence"
    elif "confidence" in merged.columns:
        base_col = "confidence"
    else:
        raise ValueError(
            "Signals file must contain either adjusted_confidence or confidence."
        )

    merged["pre_deformation_confidence"] = merged[base_col].astype(float)

    merged["deformation_adjusted_confidence"] = (
        merged["pre_deformation_confidence"] * merged["deformation_weight"]
    )

    # Keep exporter compatibility: many downstream scripts use adjusted_confidence.
    merged["adjusted_confidence"] = merged["deformation_adjusted_confidence"]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    merged.to_parquet(out_path, index=False)

    print(f"Saved {len(merged):,} rows -> {out_path}")
    print()
    print("Weights:")
    for state, weight in weight_map.items():
        print(f"  {state}: {weight:.2f}")

    print()
    print("Signal counts by compression_state:")
    print(merged["compression_state"].value_counts(dropna=False).to_string())

    print()
    print("Confidence summary by compression_state:")
    summary = (
        merged.groupby("compression_state", dropna=False)
        .agg(
            signals=(
                ("ticker", "size") if "ticker" in merged.columns else ("date", "size")
            ),
            avg_pre_confidence=("pre_deformation_confidence", "mean"),
            avg_deformation_weight=("deformation_weight", "mean"),
            avg_adjusted_confidence=("adjusted_confidence", "mean"),
            avg_market_compression_score=("market_compression_score", "mean"),
        )
        .reset_index()
        .sort_values("avg_adjusted_confidence", ascending=False)
    )
    print(summary.to_string(index=False))

    print()
    print("Tail:")
    print(
        merged[
            [
                "date",
                "ticker",
                "direction",
                "confidence",
                "pre_deformation_confidence",
                "compression_state",
                "deformation_weight",
                "adjusted_confidence",
            ]
        ]
        .tail(30)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
