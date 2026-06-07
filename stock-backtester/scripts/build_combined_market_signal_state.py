# scripts/build_combined_market_signal_state.py

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
        description="Build combined market signal state table for pseudo-allocator and market fabric."
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals_context_adjusted.parquet",
    )
    parser.add_argument(
        "--context",
        default="outputs/context/market_context_with_regime_deformation.parquet",
    )
    parser.add_argument(
        "--ticker-sensitivity",
        default="outputs/correlation/regime_ticker_stress_sensitivity.csv",
    )
    parser.add_argument(
        "--out",
        default="outputs/allocator/combined_market_signal_state.parquet",
    )
    parser.add_argument(
        "--latest-out",
        default="outputs/allocator/combined_market_signal_state_latest.csv",
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


def normalize_ticker(s: pd.Series) -> pd.Series:
    return s.astype(str).str.upper().str.strip().str.replace(".", "-", regex=False)


def load_signals(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path).copy()

    required = {"date", "ticker"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Signals missing required columns: {sorted(missing)}")

    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = normalize_ticker(df["ticker"])

    if "direction" not in df.columns:
        df["direction"] = "long"

    df["direction"] = df["direction"].astype(str).str.lower().str.strip()

    return df


def load_context(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path).copy()

    if "date" not in df.columns:
        raise ValueError("Context file must contain date column.")

    df["date"] = pd.to_datetime(df["date"])

    rename_map = {
        "realized_vol": "market_realized_vol",
        "realized_vol_z": "market_realized_vol_z",
        "return_entropy": "market_return_entropy",
        "entropy_z": "market_entropy_z",
        "volatility_state": "market_volatility_state",
        "entropy_state": "market_entropy_state",
        "volatility_weight": "market_volatility_weight",
        "entropy_weight": "market_entropy_weight",
        "context_weight": "market_context_weight",
        "pair_count": "deformation_pair_count",
    }

    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    wanted = [
        "date",
        "market_return",
        "market_realized_vol",
        "market_realized_vol_z",
        "cross_sectional_dispersion",
        "market_return_entropy",
        "market_entropy_z",
        "market_volatility_state",
        "market_entropy_state",
        "market_volatility_weight",
        "market_entropy_weight",
        "market_context_weight",
        "avg_corr",
        "avg_calm_baseline_corr",
        "avg_stress_baseline_corr",
        "market_compression_score",
        "stress_distance_score",
        "pairs_above_calm_baseline",
        "pairs_below_calm_baseline",
        "deformation_pair_count",
        "compression_state",
        "compression_percentile",
        "fragmentation_percentile",
    ]

    existing = [c for c in wanted if c in df.columns]
    return df[existing].drop_duplicates("date")


def load_ticker_sensitivity(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=["ticker"])

    df = pd.read_csv(p).copy()

    if "ticker" not in df.columns:
        return pd.DataFrame(columns=["ticker"])

    df["ticker"] = normalize_ticker(df["ticker"])

    rename_map = {
        "pair_count": "ticker_sensitivity_pair_count",
    }

    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    wanted = [
        "ticker",
        "ticker_stress_sensitivity",
        "median_stress_sensitivity",
        "calm_avg_corr",
        "stress_avg_corr",
        "ticker_sensitivity_pair_count",
        "stress_sensitivity_rank",
    ]

    existing = [c for c in wanted if c in df.columns]
    return df[existing].drop_duplicates("ticker")


def compression_group(state: object) -> str:
    s = str(state).upper().strip()

    if s in {"BROAD_COMPRESSION", "MODERATE_COMPRESSION"}:
        return "compression"
    if s in {"BROAD_FRAGMENTATION", "MODERATE_FRAGMENTATION"}:
        return "fragmentation"
    if s == "STABLE":
        return "stable"

    return "unknown"


def edge_mode(group: object) -> str:
    g = str(group).lower().strip()

    if g == "compression":
        return "tighten_edges"
    if g == "fragmentation":
        return "loosen_edges"

    return "normal_edges"


def main() -> None:
    args = parse_args()

    signals = load_signals(args.signals)
    context = load_context(args.context)
    ticker_sensitivity = load_ticker_sensitivity(args.ticker_sensitivity)

    merged = signals.merge(context, on="date", how="left")

    if not ticker_sensitivity.empty:
        merged = merged.merge(ticker_sensitivity, on="ticker", how="left")

    if "compression_state" not in merged.columns:
        merged["compression_state"] = "UNKNOWN"

    merged["compression_state"] = (
        merged["compression_state"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    weight_map = build_weight_map(args)

    merged["deformation_weight"] = (
        merged["compression_state"].map(weight_map).fillna(1.0).astype(float)
    )

    if "adjusted_confidence" in merged.columns:
        base_col = "adjusted_confidence"
    elif "confidence" in merged.columns:
        base_col = "confidence"
    else:
        raise ValueError("Signals must contain adjusted_confidence or confidence.")

    merged["pre_allocator_confidence"] = merged[base_col].astype(float)

    merged["deformation_adjusted_confidence"] = (
        merged["pre_allocator_confidence"] * merged["deformation_weight"]
    )

    if "ticker_stress_sensitivity" not in merged.columns:
        merged["ticker_stress_sensitivity"] = 0.0

    merged["ticker_stress_sensitivity"] = (
        merged["ticker_stress_sensitivity"].fillna(0.0).astype(float)
    )

    merged["ticker_stress_sensitivity_weight"] = (
        1.0 + merged["ticker_stress_sensitivity"].clip(-0.10, 0.10)
    )

    merged["final_signal_score"] = (
        merged["deformation_adjusted_confidence"]
        * merged["ticker_stress_sensitivity_weight"]
    )

    merged["allocator_rank"] = (
        merged.groupby("date")["final_signal_score"]
        .rank(method="first", ascending=False)
    )

    merged["fabric_regime_group"] = merged["compression_state"].apply(compression_group)
    merged["fabric_edge_mode"] = merged["fabric_regime_group"].apply(edge_mode)

    merged["signal_state_label"] = (
        merged["fabric_regime_group"].astype(str)
        + "_"
        + merged.get("market_volatility_state", pd.Series("unknown", index=merged.index)).astype(str)
        + "_"
        + merged.get("market_entropy_state", pd.Series("unknown", index=merged.index)).astype(str)
    )

    preferred = [
        "date",
        "ticker",
        "direction",
        "engine",
        "window",
        "horizon",

        "raw_score",
        "normalized_score",
        "peer_spread_z",
        "top_k_avg_corr",
        "peer_spread",
        "stock_return",
        "peer_basket_return",
        "peer_1",
        "peer_2",
        "peer_3",
        "peer_4",
        "peer_5",

        "confidence",
        "adjusted_confidence",
        "pre_allocator_confidence",
        "deformation_adjusted_confidence",
        "final_signal_score",
        "allocator_rank",

        "market_context_weight",
        "market_volatility_state",
        "market_entropy_state",
        "market_volatility_weight",
        "market_entropy_weight",
        "market_realized_vol",
        "market_realized_vol_z",
        "market_return_entropy",
        "market_entropy_z",
        "cross_sectional_dispersion",

        "market_compression_score",
        "compression_state",
        "compression_percentile",
        "fragmentation_percentile",
        "deformation_weight",
        "fabric_regime_group",
        "fabric_edge_mode",
        "signal_state_label",

        "ticker_stress_sensitivity",
        "ticker_stress_sensitivity_weight",
        "median_stress_sensitivity",
        "calm_avg_corr",
        "stress_avg_corr",
        "stress_sensitivity_rank",
    ]

    existing = [c for c in preferred if c in merged.columns]
    remaining = [c for c in merged.columns if c not in existing]
    merged = merged[existing + remaining]

    out = Path(args.out)
    latest_out = Path(args.latest_out)

    out.parent.mkdir(parents=True, exist_ok=True)
    latest_out.parent.mkdir(parents=True, exist_ok=True)

    merged.to_parquet(out, index=False)

    latest_date = merged["date"].max()
    latest = (
        merged[merged["date"].eq(latest_date)]
        .sort_values("final_signal_score", ascending=False)
        .head(100)
    )

    latest.to_csv(latest_out, index=False)

    print(f"Saved combined market signal state: {len(merged):,} rows -> {out}")
    print(f"Saved latest preview: {len(latest):,} rows -> {latest_out}")
    print()
    print("Latest date:", latest_date.date())
    print()
    print(
        latest[
            [
                "date",
                "ticker",
                "direction",
                "horizon",
                "confidence",
                "adjusted_confidence",
                "compression_state",
                "fabric_regime_group",
                "deformation_weight",
                "ticker_stress_sensitivity",
                "final_signal_score",
                "allocator_rank",
            ]
        ].to_string(index=False)
    )

    print()
    print("State summary:")
    print(
        merged.groupby(["compression_state", "fabric_regime_group"], dropna=False)
        .agg(
            signals=("ticker", "size"),
            avg_final_signal_score=("final_signal_score", "mean"),
            avg_deformation_weight=("deformation_weight", "mean"),
            avg_ticker_stress_sensitivity=("ticker_stress_sensitivity", "mean"),
        )
        .reset_index()
        .sort_values("avg_final_signal_score", ascending=False)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
