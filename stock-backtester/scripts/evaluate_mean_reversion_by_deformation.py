# scripts/evaluate_mean_reversion_by_deformation.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate mean-reversion signal performance by market correlation "
            "deformation state."
        )
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_evaluation.parquet",
        help="Mean-reversion evaluation parquet file.",
    )
    parser.add_argument(
        "--context",
        default="outputs/context/market_context_with_regime_deformation.parquet",
        help="Market context file containing regime deformation features.",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=20,
        help="Future return horizon to evaluate, e.g. 1, 5, 10, 20.",
    )
    parser.add_argument(
        "--out",
        default="outputs/reports/mean_reversion_by_deformation.csv",
        help="Output CSV path.",
    )

    return parser.parse_args()


def resolve_return_column(df: pd.DataFrame, horizon: int | None) -> str:
    """
    Pick the future-return column to evaluate.

    Your current schema has:
        future_return_1d
        future_return_5d
        future_return_10d
        future_return_20d
    """

    if horizon is not None:
        col = f"future_return_{horizon}d"

        if col not in df.columns:
            raise ValueError(
                f"Requested horizon={horizon}, but {col!r} was not found. "
                f"Available columns: {', '.join(df.columns)}"
            )

        return col

    candidates = [
        "future_return_20d",
        "future_return_10d",
        "future_return_5d",
        "future_return_1d",
        "forward_return",
        "future_return",
        "realized_return",
        "trade_return",
        "return",
        "pnl",
    ]

    for col in candidates:
        if col in df.columns:
            return col

    raise ValueError(
        "Could not find return column. Available columns: " + ", ".join(df.columns)
    )


def add_strategy_return(
    signals: pd.DataFrame,
    raw_return_col: str,
) -> pd.DataFrame:
    """
    Convert raw future returns into strategy returns.

    Long signal:
        strategy_return = future_return

    Short signal:
        strategy_return = -future_return
    """

    out = signals.copy()
    out["strategy_return"] = out[raw_return_col]

    if "direction" in out.columns:
        direction = out["direction"].astype(str).str.lower().str.strip()

        short_mask = direction.eq("short")

        out.loc[short_mask, "strategy_return"] = -out.loc[
            short_mask,
            raw_return_col,
        ]

    return out


def summarize_group(
    df: pd.DataFrame,
    group_cols: list[str],
    ret_col: str,
) -> pd.DataFrame:
    """
    Summarize signal performance by one or more grouping columns.
    """

    grouped = (
        df.groupby(group_cols, dropna=False)
        .agg(
            trades=(ret_col, "size"),
            avg_return=(ret_col, "mean"),
            median_return=(ret_col, "median"),
            win_rate=(ret_col, lambda x: float((x > 0).mean())),
            avg_confidence=(
                (
                    "confidence",
                    "mean",
                )
                if "confidence" in df.columns
                else (ret_col, "size")
            ),
            avg_peer_spread_z=(
                (
                    "peer_spread_z",
                    "mean",
                )
                if "peer_spread_z" in df.columns
                else (ret_col, "size")
            ),
            avg_top_k_avg_corr=(
                (
                    "top_k_avg_corr",
                    "mean",
                )
                if "top_k_avg_corr" in df.columns
                else (ret_col, "size")
            ),
            avg_market_compression_score=("market_compression_score", "mean"),
            avg_compression_percentile=("compression_percentile", "mean"),
            avg_fragmentation_percentile=("fragmentation_percentile", "mean"),
            avg_context_weight=("context_weight", "mean"),
        )
        .reset_index()
    )

    grouped["total_return_sum"] = (
        df.groupby(group_cols, dropna=False)[ret_col].sum().values
    )

    grouped = grouped.sort_values(
        ["avg_return", "win_rate", "trades"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    return grouped


def main() -> None:
    args = parse_args()

    signals = pd.read_parquet(args.signals)
    context = pd.read_parquet(args.context)

    if "date" not in signals.columns:
        raise ValueError("Signals file must contain a 'date' column.")

    if "date" not in context.columns:
        raise ValueError("Context file must contain a 'date' column.")

    signals["date"] = pd.to_datetime(signals["date"])
    context["date"] = pd.to_datetime(context["date"])

    raw_ret_col = resolve_return_column(signals, args.horizon)
    signals = add_strategy_return(signals, raw_ret_col)
    ret_col = "strategy_return"

    context_cols = [
        "date",
        "volatility_state",
        "entropy_state",
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

    missing_context_cols = [col for col in context_cols if col not in context.columns]

    if missing_context_cols:
        raise ValueError(
            "Context file is missing required deformation columns: "
            + ", ".join(missing_context_cols)
        )

    merged = signals.merge(
        context[context_cols],
        on="date",
        how="left",
    )

    if merged["compression_state"].isna().all():
        raise ValueError(
            "No compression_state values matched after merging on date. "
            "Check that signal dates overlap with the deformation context dates."
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    by_compression_state = summarize_group(
        merged,
        ["compression_state"],
        ret_col,
    )

    by_vol_and_compression = summarize_group(
        merged,
        ["volatility_state", "compression_state"],
        ret_col,
    )

    by_entropy_and_compression = summarize_group(
        merged,
        ["entropy_state", "compression_state"],
        ret_col,
    )

    direction_summary = None
    if "direction" in merged.columns:
        direction_summary = summarize_group(
            merged,
            ["direction", "compression_state"],
            ret_col,
        )

    by_compression_state.to_csv(out_path, index=False)

    stem = out_path.with_suffix("")
    by_vol_and_compression.to_csv(
        f"{stem}_by_volatility.csv",
        index=False,
    )
    by_entropy_and_compression.to_csv(
        f"{stem}_by_entropy.csv",
        index=False,
    )

    if direction_summary is not None:
        direction_summary.to_csv(
            f"{stem}_by_direction.csv",
            index=False,
        )

    print(f"Using raw return column: {raw_ret_col}")
    print(f"Using evaluated return: {ret_col}")
    print(f"Saved compression-state summary -> {out_path}")
    print(f"Saved volatility/compression summary -> {stem}_by_volatility.csv")
    print(f"Saved entropy/compression summary -> {stem}_by_entropy.csv")

    if direction_summary is not None:
        print(f"Saved direction/compression summary -> {stem}_by_direction.csv")

    print("\n" + "=" * 90)
    print("MEAN REVERSION BY CORRELATION DEFORMATION STATE")
    print("=" * 90)
    print(by_compression_state.to_string(index=False))

    print("\n" + "=" * 90)
    print("MEAN REVERSION BY VOLATILITY + DEFORMATION")
    print("=" * 90)
    print(by_vol_and_compression.to_string(index=False))

    print("\n" + "=" * 90)
    print("MEAN REVERSION BY ENTROPY + DEFORMATION")
    print("=" * 90)
    print(by_entropy_and_compression.to_string(index=False))

    if direction_summary is not None:
        print("\n" + "=" * 90)
        print("MEAN REVERSION BY DIRECTION + DEFORMATION")
        print("=" * 90)
        print(direction_summary.to_string(index=False))


if __name__ == "__main__":
    main()
