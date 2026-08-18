# research/correlation/evaluate_mean_reversion_by_deformation_yearly.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate mean-reversion by deformation state year by year."
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_evaluation.parquet",
    )
    parser.add_argument(
        "--context",
        default="outputs/context/market_context_with_regime_deformation.parquet",
    )
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument(
        "--out",
        default="outputs/reports/mean_reversion_by_deformation_yearly.csv",
    )

    return parser.parse_args()


def resolve_return_column(df: pd.DataFrame, horizon: int) -> str:
    col = f"future_return_{horizon}d"

    if col not in df.columns:
        raise ValueError(f"Missing {col}. Available columns: {', '.join(df.columns)}")

    return col


def add_strategy_return(df: pd.DataFrame, raw_return_col: str) -> pd.DataFrame:
    out = df.copy()
    out["strategy_return"] = out[raw_return_col]

    if "direction" in out.columns:
        direction = out["direction"].astype(str).str.lower().str.strip()
        short_mask = direction.eq("short")
        out.loc[short_mask, "strategy_return"] = -out.loc[short_mask, raw_return_col]

    return out


def main() -> None:
    args = parse_args()

    signals = pd.read_parquet(args.signals)
    context = pd.read_parquet(args.context)

    signals["date"] = pd.to_datetime(signals["date"])
    context["date"] = pd.to_datetime(context["date"])

    raw_ret_col = resolve_return_column(signals, args.horizon)
    signals = add_strategy_return(signals, raw_ret_col)

    context_cols = [
        "date",
        "volatility_state",
        "entropy_state",
        "context_weight",
        "market_compression_score",
        "compression_state",
        "compression_percentile",
        "fragmentation_percentile",
    ]

    merged = signals.merge(
        context[context_cols],
        on="date",
        how="left",
    )

    if merged["compression_state"].isna().all():
        raise ValueError("No deformation context matched signal dates.")

    merged["year"] = merged["date"].dt.year

    out = (
        merged.groupby(["year", "compression_state"], dropna=False)
        .agg(
            trades=("strategy_return", "size"),
            avg_return=("strategy_return", "mean"),
            median_return=("strategy_return", "median"),
            win_rate=("strategy_return", lambda x: float((x > 0).mean())),
            avg_confidence=("confidence", "mean"),
            avg_peer_spread_z=("peer_spread_z", "mean"),
            avg_top_k_avg_corr=("top_k_avg_corr", "mean"),
            avg_market_compression_score=("market_compression_score", "mean"),
            avg_compression_percentile=("compression_percentile", "mean"),
            avg_fragmentation_percentile=("fragmentation_percentile", "mean"),
            avg_context_weight=("context_weight", "mean"),
            total_return_sum=("strategy_return", "sum"),
        )
        .reset_index()
        .sort_values(["year", "avg_return"], ascending=[True, False])
        .reset_index(drop=True)
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)

    print(f"Using raw return column: {raw_ret_col}")
    print(f"Saved {len(out):,} rows -> {out_path}")
    print()
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
