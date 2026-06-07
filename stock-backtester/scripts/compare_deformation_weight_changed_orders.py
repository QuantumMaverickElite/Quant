# scripts/compare_deformation_weight_changed_orders.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare baseline vs deformation-weighted Rust orders."
    )

    parser.add_argument(
        "--baseline-orders",
        default="outputs/rust_inputs/h100_context_adjusted_baseline/orders.csv",
    )
    parser.add_argument(
        "--weighted-orders",
        default="outputs/rust_inputs/h100_deformation_weighted_soft_bf085/orders.csv",
    )
    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals_deformation_weighted_soft.parquet",
    )
    parser.add_argument(
        "--eval",
        default="outputs/signals/mean_reversion_evaluation.parquet",
    )
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument(
        "--out",
        default="outputs/reports/deformation_weight_changed_orders.csv",
    )
    parser.add_argument(
        "--summary-out",
        default="outputs/reports/deformation_weight_changed_orders_summary.csv",
    )

    return parser.parse_args()


def load_orders(path: str, label: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    required = {"signal_date", "ticker"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"{label} orders missing columns: {sorted(missing)}. "
            f"Available columns: {list(df.columns)}"
        )

    out = df.copy()
    out["date"] = pd.to_datetime(out["signal_date"])
    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()

    keep_cols = [
        "date",
        "signal_date",
        "entry_date",
        "exit_date",
        "ticker",
        "adjusted_confidence",
        "peer_spread_z",
    ]
    keep_cols = [col for col in keep_cols if col in out.columns]

    return out[keep_cols].drop_duplicates(["date", "ticker"])


def load_signals(path: str, horizon: int) -> pd.DataFrame:
    df = pd.read_parquet(path).copy()

    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()

    if "horizon" in df.columns:
        df = df[df["horizon"].eq(horizon)].copy()

    cols = [
        "date",
        "ticker",
        "horizon",
        "direction",
        "confidence",
        "adjusted_confidence",
        "pre_deformation_confidence",
        "deformation_weight",
        "compression_state",
        "market_compression_score",
        "compression_percentile",
        "fragmentation_percentile",
        "peer_spread_z",
        "top_k_avg_corr",
    ]
    cols = [col for col in cols if col in df.columns]

    return df[cols].drop_duplicates(["date", "ticker"])


def load_evaluation(path: str, horizon: int) -> pd.DataFrame:
    df = pd.read_parquet(path).copy()

    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()

    if "horizon" in df.columns:
        df = df[df["horizon"].eq(horizon)].copy()

    raw_return_col = f"future_return_{horizon}d"

    if raw_return_col not in df.columns:
        raise ValueError(
            f"Missing {raw_return_col}. Available columns: {list(df.columns)}"
        )

    df["strategy_return"] = df[raw_return_col]

    if "direction" in df.columns:
        direction = df["direction"].astype(str).str.lower().str.strip()
        short_mask = direction.eq("short")
        df.loc[short_mask, "strategy_return"] = -df.loc[short_mask, raw_return_col]

    cols = [
        "date",
        "ticker",
        "horizon",
        "direction",
        raw_return_col,
        "strategy_return",
        "confidence",
        "peer_spread_z",
        "top_k_avg_corr",
    ]
    cols = [col for col in cols if col in df.columns]

    return df[cols].drop_duplicates(["date", "ticker"])


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("change_type", dropna=False)
        .agg(
            orders=("ticker", "size"),
            tickers=("ticker", "nunique"),
            matched_returns=("strategy_return", lambda x: int(x.notna().sum())),
            avg_strategy_return=("strategy_return", "mean"),
            median_strategy_return=("strategy_return", "median"),
            win_rate=(
                "strategy_return",
                lambda x: (
                    float((x.dropna() > 0).mean()) if x.notna().any() else float("nan")
                ),
            ),
            total_strategy_return=("strategy_return", "sum"),
            avg_pre_deformation_confidence=("pre_deformation_confidence", "mean"),
            avg_adjusted_confidence=("adjusted_confidence", "mean"),
            avg_deformation_weight=("deformation_weight", "mean"),
            avg_market_compression_score=("market_compression_score", "mean"),
        )
        .reset_index()
        .sort_values("avg_strategy_return", ascending=False, na_position="last")
    )


def summarize_by_state(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["change_type", "compression_state"], dropna=False)
        .agg(
            orders=("ticker", "size"),
            matched_returns=("strategy_return", lambda x: int(x.notna().sum())),
            avg_strategy_return=("strategy_return", "mean"),
            median_strategy_return=("strategy_return", "median"),
            win_rate=(
                "strategy_return",
                lambda x: (
                    float((x.dropna() > 0).mean()) if x.notna().any() else float("nan")
                ),
            ),
            total_strategy_return=("strategy_return", "sum"),
            avg_deformation_weight=("deformation_weight", "mean"),
            avg_market_compression_score=("market_compression_score", "mean"),
        )
        .reset_index()
        .sort_values(["change_type", "avg_strategy_return"], ascending=[True, False])
    )


def main() -> None:
    args = parse_args()

    baseline = load_orders(args.baseline_orders, "baseline")
    weighted = load_orders(args.weighted_orders, "weighted")
    signals = load_signals(args.signals, args.horizon)
    evaluation = load_evaluation(args.eval, args.horizon)

    base_keys = baseline[["date", "ticker"]].copy()
    weighted_keys = weighted[["date", "ticker"]].copy()

    base_keys["in_baseline"] = True
    weighted_keys["in_weighted"] = True

    changed = base_keys.merge(
        weighted_keys,
        on=["date", "ticker"],
        how="outer",
    )

    changed["in_baseline"] = changed["in_baseline"].fillna(False).astype(bool)
    changed["in_weighted"] = changed["in_weighted"].fillna(False).astype(bool)

    changed["change_type"] = "kept"
    changed.loc[
        changed["in_baseline"] & ~changed["in_weighted"],
        "change_type",
    ] = "removed_by_weighting"
    changed.loc[
        ~changed["in_baseline"] & changed["in_weighted"],
        "change_type",
    ] = "added_by_weighting"

    changed = changed.merge(
        signals,
        on=["date", "ticker"],
        how="left",
    )

    changed = changed.merge(
        evaluation,
        on=["date", "ticker"],
        how="left",
        suffixes=("", "_eval"),
    )

    changed = changed.sort_values(["change_type", "date", "ticker"]).reset_index(
        drop=True
    )

    summary = summarize(changed)
    by_state = summarize_by_state(changed)

    out_path = Path(args.out)
    summary_path = Path(args.summary_out)
    by_state_path = summary_path.with_name(
        summary_path.stem.replace("_summary", "_by_state") + summary_path.suffix
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    changed.to_csv(out_path, index=False)
    summary.to_csv(summary_path, index=False)
    by_state.to_csv(by_state_path, index=False)

    print(f"Saved changed orders -> {out_path}")
    print(f"Saved summary -> {summary_path}")
    print(f"Saved by-state summary -> {by_state_path}")

    print("\n" + "=" * 90)
    print("CHANGE SUMMARY")
    print("=" * 90)
    print(summary.to_string(index=False))

    print("\n" + "=" * 90)
    print("CHANGE SUMMARY BY COMPRESSION STATE")
    print("=" * 90)
    print(by_state.to_string(index=False))

    print("\n" + "=" * 90)
    print("ADDED ORDERS")
    print("=" * 90)
    added_cols = [
        "date",
        "ticker",
        "compression_state",
        "deformation_weight",
        "pre_deformation_confidence",
        "adjusted_confidence",
        "strategy_return",
        "market_compression_score",
    ]
    added_cols = [col for col in added_cols if col in changed.columns]
    print(
        changed[changed["change_type"].eq("added_by_weighting")][added_cols]
        .sort_values("date")
        .to_string(index=False)
    )

    print("\n" + "=" * 90)
    print("REMOVED ORDERS")
    print("=" * 90)
    removed_cols = added_cols
    print(
        changed[changed["change_type"].eq("removed_by_weighting")][removed_cols]
        .sort_values("date")
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
