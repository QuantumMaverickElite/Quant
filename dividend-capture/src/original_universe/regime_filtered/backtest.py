#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def load_results(outputs_dir: Path) -> pd.DataFrame:
    files = sorted(outputs_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {outputs_dir}")

    frames = []
    for f in files:
        df = pd.read_csv(f)

        name = f.stem.lower()
        hold_days = None
        if "hold-0" in name or "hold_0" in name:
            hold_days = 0
        elif "hold-1" in name or "hold_1" in name:
            hold_days = 1
        elif "hold-3" in name or "hold_3" in name:
            hold_days = 3
        elif "hold-5" in name or "hold_5" in name:
            hold_days = 5

        if hold_days is None:
            continue

        df["hold_days"] = hold_days
        df["source_file"] = f.name
        df["ex_date"] = pd.to_datetime(df["ex_date"])
        frames.append(df)

    if not frames:
        raise ValueError("No recognized hold-day CSVs found.")

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["ex_date", "ticker", "hold_days"]).reset_index(drop=True)
    return out


def label_ticker_profiles(
    df_train: pd.DataFrame,
    long_holds: tuple[int, int] = (1, 3),
) -> pd.DataFrame:
    profile_table = (
        df_train[df_train["hold_days"].isin(long_holds)]
        .groupby(["ticker", "hold_days"])["gross_return_pct"]
        .mean()
        .unstack("hold_days")
    )

    for h in long_holds:
        if h not in profile_table.columns:
            profile_table[h] = pd.NA

    def classify(row: pd.Series) -> str:
        vals = [row[h] for h in long_holds]
        if all(pd.notna(v) and v > 0 for v in vals):
            return "recovery"
        if all(pd.notna(v) and v < 0 for v in vals):
            return "continuation"
        return "neutral"

    profile_table["profile"] = profile_table.apply(classify, axis=1)
    return profile_table.reset_index()


def build_regime_series(
    df: pd.DataFrame,
    hold_for_regime: int = 1,
    rolling_window: int = 8,
    overreaction_threshold: float = 1.1,
    underreaction_threshold: float = 0.9,
) -> pd.DataFrame:
    regime_base = (
        df[df["hold_days"] == hold_for_regime]
        .groupby("ex_date", as_index=False)["drop_ratio"]
        .mean()
        .sort_values("ex_date")
        .reset_index(drop=True)
    )

    # Shift by 1 so each date only sees prior information.
    regime_base["rolling_drop_ratio"] = (
        regime_base["drop_ratio"]
        .shift(1)
        .rolling(rolling_window, min_periods=rolling_window)
        .mean()
    )

    def classify(x: float) -> str:
        if pd.isna(x):
            return "unknown"
        if x > overreaction_threshold:
            return "overreaction"
        if x < underreaction_threshold:
            return "underreaction"
        return "neutral"

    regime_base["regime"] = regime_base["rolling_drop_ratio"].apply(classify)
    return regime_base


def apply_strategy(
    df_test: pd.DataFrame,
    profile_df: pd.DataFrame,
    regime_df: pd.DataFrame,
    trade_hold_days: int = 1,
) -> pd.DataFrame:
    trade_df = df_test[df_test["hold_days"] == trade_hold_days].copy()

    trade_df = trade_df.merge(
        profile_df[["ticker", "profile"]],
        on="ticker",
        how="left",
    )
    trade_df = trade_df.merge(
        regime_df[["ex_date", "rolling_drop_ratio", "regime"]],
        on="ex_date",
        how="left",
    )

    trade_df["signal"] = "skip"

    long_mask = (
        (trade_df["profile"] == "recovery")
        & (trade_df["regime"] == "underreaction")
    )
    short_mask = (
        (trade_df["profile"] == "continuation")
        & (trade_df["regime"] == "overreaction")
    )

    trade_df.loc[long_mask, "signal"] = "long"
    trade_df.loc[short_mask, "signal"] = "short"

    trade_df["strategy_return_pct"] = 0.0
    trade_df["strategy_pnl"] = 0.0

    trade_df.loc[trade_df["signal"] == "long", "strategy_return_pct"] = trade_df.loc[
        trade_df["signal"] == "long", "gross_return_pct"
    ]
    trade_df.loc[trade_df["signal"] == "long", "strategy_pnl"] = trade_df.loc[
        trade_df["signal"] == "long", "gross_pnl"
    ]

    trade_df.loc[trade_df["signal"] == "short", "strategy_return_pct"] = -trade_df.loc[
        trade_df["signal"] == "short", "gross_return_pct"
    ]
    trade_df.loc[trade_df["signal"] == "short", "strategy_pnl"] = -trade_df.loc[
        trade_df["signal"] == "short", "gross_pnl"
    ]

    return trade_df


def summarize_strategy(df: pd.DataFrame, label: str) -> None:
    traded = df[df["signal"] != "skip"].copy()

    print(f"\n=== {label} ===")
    print(f"Rows in period:        {len(df)}")
    print(f"Trades taken:          {len(traded)}")

    if traded.empty:
        print("No trades taken.")
        return

    wins = (traded["strategy_pnl"] > 0).sum()
    losses = (traded["strategy_pnl"] <= 0).sum()
    avg_ret = traded["strategy_return_pct"].mean()
    med_ret = traded["strategy_return_pct"].median()
    total_pnl = traded["strategy_pnl"].sum()
    win_rate = wins / len(traded) * 100.0

    print(f"Wins:                  {wins}")
    print(f"Losses:                {losses}")
    print(f"Win rate:              {win_rate:.2f}%")
    print(f"Average return:        {avg_ret:.4f}%")
    print(f"Median return:         {med_ret:.4f}%")
    print(f"Total strategy PnL:    ${total_pnl:,.2f}")

    print("\nBy signal:")
    by_signal = (
        traded.groupby("signal")
        .agg(
            trades=("signal", "count"),
            avg_return_pct=("strategy_return_pct", "mean"),
            total_pnl=("strategy_pnl", "sum"),
            win_rate_pct=("strategy_pnl", lambda s: (s > 0).mean() * 100.0),
        )
        .round(4)
    )
    print(by_signal.to_string())

    print("\nBy ticker:")
    by_ticker = (
        traded.groupby("ticker")
        .agg(
            trades=("ticker", "count"),
            avg_return_pct=("strategy_return_pct", "mean"),
            total_pnl=("strategy_pnl", "sum"),
            win_rate_pct=("strategy_pnl", lambda s: (s > 0).mean() * 100.0),
        )
        .sort_values("total_pnl", ascending=False)
        .round(4)
    )
    print(by_ticker.to_string())


def summarize_profiles(profile_df: pd.DataFrame) -> None:
    print("\n=== TRAINED TICKER PROFILES ===")
    print(profile_df.sort_values("ticker").to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Regime-filtered dividend event backtest")
    parser.add_argument("--outputs-dir", default="../outputs")
    parser.add_argument("--train-end", default="2021-12-31")
    parser.add_argument("--test-start", default="2022-01-01")
    parser.add_argument("--trade-hold", type=int, default=1)
    parser.add_argument("--regime-hold", type=int, default=1)
    parser.add_argument("--rolling-window", type=int, default=8)
    parser.add_argument("--overreaction-threshold", type=float, default=1.1)
    parser.add_argument("--underreaction-threshold", type=float, default=0.9)
    parser.add_argument("--output-dir", required=True, help="Directory where results will be saved",)
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    df = load_results(outputs_dir)

    train_end = pd.Timestamp(args.train_end)
    test_start = pd.Timestamp(args.test_start)

    df_train = df[df["ex_date"] <= train_end].copy()
    df_test = df[df["ex_date"] >= test_start].copy()

    profile_df = label_ticker_profiles(df_train, long_holds=(1, 3))
    regime_df = build_regime_series(
        df=df,
        hold_for_regime=args.regime_hold,
        rolling_window=args.rolling_window,
        overreaction_threshold=args.overreaction_threshold,
        underreaction_threshold=args.underreaction_threshold,
    )

    summarize_profiles(profile_df)

    strategy_df = apply_strategy(
        df_test=df_test,
        profile_df=profile_df,
        regime_df=regime_df,
        trade_hold_days=args.trade_hold,
    )

    summarize_strategy(strategy_df, label="TEST PERIOD STRATEGY SUMMARY")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    save_path = output_dir / "regime_filtered_test_trades.csv"
    strategy_df.to_csv(save_path, index=False)
    print(f"\nSaved test trades to: {save_path}")

if __name__ == "__main__":
    main()
