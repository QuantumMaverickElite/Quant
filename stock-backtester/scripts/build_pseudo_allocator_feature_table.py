# scripts/build_pseudo_allocator_feature_table.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_DEFORMATION_WEIGHTS = {
    "BROAD_COMPRESSION": 1.15,
    "MODERATE_COMPRESSION": 1.05,
    "STABLE": 1.00,
    "BROAD_FRAGMENTATION": 0.85,
    "MODERATE_FRAGMENTATION": 0.75,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build pseudo-allocator feature table with deformation features."
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals_context_adjusted.parquet",
        help="Context-adjusted mean-reversion signals.",
    )
    parser.add_argument(
        "--context",
        default="outputs/context/market_context_with_regime_deformation.parquet",
        help="Market context with volatility, entropy, and deformation features.",
    )
    parser.add_argument(
        "--ticker-sensitivity",
        default="outputs/correlation/regime_ticker_stress_sensitivity.csv",
        help="Ticker-level regime stress sensitivity file.",
    )
    parser.add_argument(
        "--out",
        default="outputs/allocator/pseudo_allocator_feature_table.parquet",
        help="Output allocator feature table.",
    )
    parser.add_argument(
        "--csv-out",
        default="outputs/allocator/pseudo_allocator_feature_table_latest.csv",
        help="Latest-date CSV preview.",
    )

    parser.add_argument("--broad-compression-weight", type=float, default=1.15)
    parser.add_argument("--moderate-compression-weight", type=float, default=1.05)
    parser.add_argument("--stable-weight", type=float, default=1.00)
    parser.add_argument("--broad-fragmentation-weight", type=float, default=0.85)
    parser.add_argument("--moderate-fragmentation-weight", type=float, default=0.75)

    return parser.parse_args()


def build_weight_map(args: argparse.Namespace) -> dict[str, float]:
    return {
        "BROAD_COMPRESSION": args.broad_compression_weight,
        "MODERATE_COMPRESSION": args.moderate_compression_weight,
        "STABLE": args.stable_weight,
        "BROAD_FRAGMENTATION": args.broad_fragmentation_weight,
        "MODERATE_FRAGMENTATION": args.moderate_fragmentation_weight,
    }


def load_signals(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path).copy()

    if "date" not in df.columns:
        raise ValueError("Signals file must contain a date column.")

    if "ticker" not in df.columns:
        raise ValueError("Signals file must contain a ticker column.")

    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()

    if "direction" not in df.columns:
        df["direction"] = "long"

    df["direction"] = df["direction"].astype(str).str.lower().str.strip()

    return df


def load_context(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path).copy()

    if "date" not in df.columns:
        raise ValueError("Context file must contain a date column.")

    df["date"] = pd.to_datetime(df["date"])

    wanted_cols = [
        "date",
        "market_return",
        "realized_vol",
        "realized_vol_z",
        "cross_sectional_dispersion",
        "return_entropy",
        "entropy_z",
        "volatility_state",
        "entropy_state",
        "volatility_weight",
        "entropy_weight",
        "context_weight",
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

    existing = [col for col in wanted_cols if col in df.columns]

    return df[existing].drop_duplicates("date")


def load_ticker_sensitivity(path: str) -> pd.DataFrame:
    p = Path(path)

    if not p.exists():
        return pd.DataFrame(columns=["ticker"])

    df = pd.read_csv(p).copy()

    if "ticker" not in df.columns:
        return pd.DataFrame(columns=["ticker"])

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()

    wanted_cols = [
        "ticker",
        "ticker_stress_sensitivity",
        "median_stress_sensitivity",
        "calm_avg_corr",
        "stress_avg_corr",
        "pair_count",
        "stress_sensitivity_rank",
    ]

    existing = [col for col in wanted_cols if col in df.columns]

    return df[existing].drop_duplicates("ticker")


def main() -> None:
    args = parse_args()

    signals = load_signals(args.signals)
    context = load_context(args.context)
    ticker_sensitivity = load_ticker_sensitivity(args.ticker_sensitivity)

    merged = signals.merge(
        context,
        on="date",
        how="left",
        suffixes=("", "_context"),
    )

    if not ticker_sensitivity.empty:
        merged = merged.merge(
            ticker_sensitivity,
            on="ticker",
            how="left",
        )

    weight_map = build_weight_map(args)

    merged["compression_state"] = (
        merged["compression_state"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    merged["deformation_weight"] = (
        merged["compression_state"]
        .map(weight_map)
        .fillna(1.0)
        .astype(float)
    )

    if "adjusted_confidence" in merged.columns:
        base_conf_col = "adjusted_confidence"
    elif "confidence" in merged.columns:
        base_conf_col = "confidence"
    else:
        raise ValueError("Signals must contain adjusted_confidence or confidence.")

    merged["pre_allocator_confidence"] = merged[base_conf_col].astype(float)

    merged["deformation_adjusted_confidence"] = (
        merged["pre_allocator_confidence"] * merged["deformation_weight"]
    )

    if "ticker_stress_sensitivity" in merged.columns:
        # Mild ticker-level penalty/boost. Keep subtle for now.
        merged["ticker_stress_sensitivity"] = merged["ticker_stress_sensitivity"].fillna(0.0)

        merged["ticker_stress_sensitivity_weight"] = (
            1.0 + merged["ticker_stress_sensitivity"].clip(-0.10, 0.10)
        )
    else:
        merged["ticker_stress_sensitivity"] = 0.0
        merged["ticker_stress_sensitivity_weight"] = 1.0

    merged["final_signal_score"] = (
        merged["deformation_adjusted_confidence"]
        * merged["ticker_stress_sensitivity_weight"]
    )

    merged["allocator_rank"] = (
        merged.groupby("date")["final_signal_score"]
        .rank(method="first", ascending=False)
    )

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
        "compression_percentile",
        "fragmentation_percentile",
        "deformation_weight",
        "deformation_adjusted_confidence",
        "ticker_stress_sensitivity",
        "ticker_stress_sensitivity_weight",
        "final_signal_score",
        "allocator_rank",
        "peer_spread_z",
        "top_k_avg_corr",
        "realized_vol_z",
        "entropy_z",
    ]

    existing_preferred = [col for col in preferred_cols if col in merged.columns]
    remaining = [col for col in merged.columns if col not in existing_preferred]
    merged = merged[existing_preferred + remaining]

    out_path = Path(args.out)
    csv_path = Path(args.csv_out)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    merged.to_parquet(out_path, index=False)

    latest_date = merged["date"].max()
    latest = (
        merged[merged["date"].eq(latest_date)]
        .sort_values("final_signal_score", ascending=False)
        .head(50)
    )

    latest.to_csv(csv_path, index=False)

    print(f"Saved allocator feature table: {len(merged):,} rows -> {out_path}")
    print(f"Saved latest preview: {len(latest):,} rows -> {csv_path}")
    print()
    print("Latest date:", latest_date.date())
    print()
    print(
        latest[
            [
                "date",
                "ticker",
                "direction",
                "confidence",
                "adjusted_confidence",
                "compression_state",
                "deformation_weight",
                "ticker_stress_sensitivity",
                "final_signal_score",
                "allocator_rank",
            ]
        ].to_string(index=False)
    )

    print()
    print("Compression-state score summary:")
    print(
        merged.groupby("compression_state", dropna=False)
        .agg(
            signals=("ticker", "size"),
            avg_final_score=("final_signal_score", "mean"),
            avg_deformation_weight=("deformation_weight", "mean"),
            avg_ticker_stress_sensitivity=("ticker_stress_sensitivity", "mean"),
        )
        .reset_index()
        .sort_values("avg_final_score", ascending=False)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
