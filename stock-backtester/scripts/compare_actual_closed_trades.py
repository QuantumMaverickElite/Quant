# scripts/compare_actual_closed_trades.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare actual closed trades between two Rust stress runs."
    )

    parser.add_argument(
        "--baseline-trades",
        default="outputs/rust_stress/h100_context_adjusted_baseline_100k/actual_closed_trades.csv",
    )
    parser.add_argument(
        "--weighted-trades",
        default="outputs/rust_stress/h100_deformation_weighted_soft_bf085_100k/actual_closed_trades.csv",
    )
    parser.add_argument(
        "--weighted-signals",
        default="outputs/signals/mean_reversion_signals_deformation_weighted_soft.parquet",
    )
    parser.add_argument(
        "--out",
        default="outputs/reports/deformation_actual_closed_trade_changes.csv",
    )
    parser.add_argument(
        "--summary-out",
        default="outputs/reports/deformation_actual_closed_trade_changes_summary.csv",
    )

    return parser.parse_args()


def load_trades(path: str, label: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    required = {
        "signal_date",
        "entry_date",
        "exit_date",
        "ticker",
        "direction",
        "pnl",
        "trade_return",
        "adjusted_confidence",
        "peer_spread_z",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{label} trades missing columns: {sorted(missing)}. "
            f"Available columns: {list(df.columns)}"
        )

    out = df.copy()
    out["signal_date"] = pd.to_datetime(out["signal_date"])
    out["entry_date"] = pd.to_datetime(out["entry_date"])
    out["exit_date"] = pd.to_datetime(out["exit_date"])
    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
    out["direction"] = out["direction"].astype(str).str.lower().str.strip()

    return out


def load_weighted_signal_context(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path).copy()

    df["signal_date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()

    if "direction" in df.columns:
        df["direction"] = df["direction"].astype(str).str.lower().str.strip()
    else:
        df["direction"] = "long"

    # Rust export used signal-horizon 100, so attach the H=100 signal context.
    if "horizon" in df.columns:
        df = df[df["horizon"].eq(100)].copy()

    cols = [
        "signal_date",
        "ticker",
        "direction",
        "confidence",
        "pre_deformation_confidence",
        "deformation_weight",
        "deformation_adjusted_confidence",
        "compression_state",
        "market_compression_score",
        "compression_percentile",
        "fragmentation_percentile",
        "context_weight",
        "volatility_state",
        "entropy_state",
    ]
    cols = [col for col in cols if col in df.columns]

    return df[cols].drop_duplicates(["signal_date", "ticker", "direction"])


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("change_type", dropna=False)
        .agg(
            trades=("ticker", "size"),
            tickers=("ticker", "nunique"),
            avg_trade_return=("trade_return", "mean"),
            median_trade_return=("trade_return", "median"),
            win_rate=("trade_return", lambda x: float((x > 0).mean())),
            total_pnl=("pnl", "sum"),
            avg_pnl=("pnl", "mean"),
            avg_adjusted_confidence=("adjusted_confidence", "mean"),
            avg_peer_spread_z=("peer_spread_z", "mean"),
            avg_deformation_weight=("deformation_weight", "mean"),
            avg_market_compression_score=("market_compression_score", "mean"),
        )
        .reset_index()
        .sort_values("avg_trade_return", ascending=False)
    )


def summarize_by_state(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["change_type", "compression_state"], dropna=False)
        .agg(
            trades=("ticker", "size"),
            tickers=("ticker", "nunique"),
            avg_trade_return=("trade_return", "mean"),
            median_trade_return=("trade_return", "median"),
            win_rate=("trade_return", lambda x: float((x > 0).mean())),
            total_pnl=("pnl", "sum"),
            avg_pnl=("pnl", "mean"),
            avg_adjusted_confidence=("adjusted_confidence", "mean"),
            avg_deformation_weight=("deformation_weight", "mean"),
            avg_market_compression_score=("market_compression_score", "mean"),
        )
        .reset_index()
        .sort_values(["change_type", "avg_trade_return"], ascending=[True, False])
    )


def main() -> None:
    args = parse_args()

    baseline = load_trades(args.baseline_trades, "baseline")
    weighted = load_trades(args.weighted_trades, "weighted")
    signal_context = load_weighted_signal_context(args.weighted_signals)

    key_cols = ["signal_date", "entry_date", "exit_date", "ticker", "direction"]

    baseline_keys = baseline[key_cols].copy()
    weighted_keys = weighted[key_cols].copy()

    baseline_keys["in_baseline"] = True
    weighted_keys["in_weighted"] = True

    changed = baseline_keys.merge(
        weighted_keys,
        on=key_cols,
        how="outer",
    )

    changed["in_baseline"] = (
        changed["in_baseline"]
        .where(
            changed["in_baseline"].notna(),
            False,
        )
        .astype(bool)
    )

    changed["in_weighted"] = (
        changed["in_weighted"]
        .where(
            changed["in_weighted"].notna(),
            False,
        )
        .astype(bool)
    )

    changed["change_type"] = "kept"
    changed.loc[
        changed["in_baseline"] & ~changed["in_weighted"],
        "change_type",
    ] = "removed_by_weighting"
    changed.loc[
        ~changed["in_baseline"] & changed["in_weighted"],
        "change_type",
    ] = "added_by_weighting"

    baseline_metrics = baseline[
        key_cols
        + [
            "pnl",
            "trade_return",
            "adjusted_confidence",
            "peer_spread_z",
            "entry_value",
            "exit_value",
        ]
    ].copy()

    weighted_metrics = weighted[
        key_cols
        + [
            "pnl",
            "trade_return",
            "adjusted_confidence",
            "peer_spread_z",
            "entry_value",
            "exit_value",
        ]
    ].copy()

    baseline_metrics = baseline_metrics.rename(
        columns={
            "pnl": "baseline_pnl",
            "trade_return": "baseline_trade_return",
            "adjusted_confidence": "baseline_adjusted_confidence",
            "peer_spread_z": "baseline_peer_spread_z",
            "entry_value": "baseline_entry_value",
            "exit_value": "baseline_exit_value",
        }
    )

    weighted_metrics = weighted_metrics.rename(
        columns={
            "pnl": "weighted_pnl",
            "trade_return": "weighted_trade_return",
            "adjusted_confidence": "weighted_adjusted_confidence",
            "peer_spread_z": "weighted_peer_spread_z",
            "entry_value": "weighted_entry_value",
            "exit_value": "weighted_exit_value",
        }
    )

    changed = changed.merge(baseline_metrics, on=key_cols, how="left")
    changed = changed.merge(weighted_metrics, on=key_cols, how="left")

    changed["pnl"] = changed["weighted_pnl"].combine_first(changed["baseline_pnl"])
    changed["trade_return"] = changed["weighted_trade_return"].combine_first(
        changed["baseline_trade_return"]
    )
    changed["adjusted_confidence"] = changed[
        "weighted_adjusted_confidence"
    ].combine_first(changed["baseline_adjusted_confidence"])
    changed["peer_spread_z"] = changed["weighted_peer_spread_z"].combine_first(
        changed["baseline_peer_spread_z"]
    )

    changed = changed.merge(
        signal_context,
        on=["signal_date", "ticker", "direction"],
        how="left",
    )

    changed = changed.sort_values(["change_type", "signal_date", "ticker"]).reset_index(
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

    print(f"Saved changed trades -> {out_path}")
    print(f"Saved summary -> {summary_path}")
    print(f"Saved by-state summary -> {by_state_path}")

    print("\n" + "=" * 90)
    print("ACTUAL CLOSED TRADE CHANGE SUMMARY")
    print("=" * 90)
    print(summary.to_string(index=False))

    print("\n" + "=" * 90)
    print("BY COMPRESSION STATE")
    print("=" * 90)
    print(by_state.to_string(index=False))

    cols = [
        "signal_date",
        "entry_date",
        "exit_date",
        "ticker",
        "direction",
        "change_type",
        "trade_return",
        "pnl",
        "adjusted_confidence",
        "peer_spread_z",
        "compression_state",
        "deformation_weight",
        "market_compression_score",
    ]
    cols = [col for col in cols if col in changed.columns]

    print("\n" + "=" * 90)
    print("ADDED BY WEIGHTING")
    print("=" * 90)
    print(
        changed[changed["change_type"].eq("added_by_weighting")][cols]
        .sort_values("trade_return", ascending=False)
        .to_string(index=False)
    )

    print("\n" + "=" * 90)
    print("REMOVED BY WEIGHTING")
    print("=" * 90)
    print(
        changed[changed["change_type"].eq("removed_by_weighting")][cols]
        .sort_values("trade_return", ascending=True)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
