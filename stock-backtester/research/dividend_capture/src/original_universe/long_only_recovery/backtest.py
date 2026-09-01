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

        df = pd.read_csv(f)
        df["hold_days"] = hold_days
        df["source_file"] = f.name
        df["ex_date"] = pd.to_datetime(df["ex_date"])
        frames.append(df)

    if not frames:
        raise ValueError("No recognized hold-day CSVs found.")

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["ex_date", "ticker", "hold_days"]).reset_index(drop=True)
    return out


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


def label_recovery_profiles(
    df_train: pd.DataFrame,
    holds: tuple[int, ...] = (1, 3),
    min_avg_return: float = 0.0,
    min_win_rate: float = 0.50,
) -> pd.DataFrame:
    rows = []

    for ticker, sub in df_train.groupby("ticker"):
        ticker_row = {"ticker": ticker, "profile": "neutral"}

        is_recovery = True

        for h in holds:
            s = sub[sub["hold_days"] == h]["gross_return_pct"].dropna()
            if s.empty:
                is_recovery = False
                ticker_row[f"hold_{h}_avg"] = pd.NA
                ticker_row[f"hold_{h}_win_rate"] = pd.NA
                continue

            avg_ret = s.mean()
            win_rate = (s > 0).mean()

            ticker_row[f"hold_{h}_avg"] = avg_ret
            ticker_row[f"hold_{h}_win_rate"] = win_rate

            if not (avg_ret > min_avg_return and win_rate >= min_win_rate):
                is_recovery = False

        if is_recovery:
            ticker_row["profile"] = "recovery"

        rows.append(ticker_row)

    return pd.DataFrame(rows).sort_values("ticker").reset_index(drop=True)


def apply_long_only_strategy(
    df_test: pd.DataFrame,
    profile_df: pd.DataFrame,
    regime_df: pd.DataFrame,
    trade_hold_days: int,
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

    # Strategy A: profile only
    trade_df["signal_profile_only"] = "skip"
    mask_profile_only = trade_df["profile"] == "recovery"
    trade_df.loc[mask_profile_only, "signal_profile_only"] = "long"

    trade_df["return_profile_only"] = 0.0
    trade_df["pnl_profile_only"] = 0.0
    trade_df.loc[mask_profile_only, "return_profile_only"] = trade_df.loc[
        mask_profile_only, "gross_return_pct"
    ]
    trade_df.loc[mask_profile_only, "pnl_profile_only"] = trade_df.loc[
        mask_profile_only, "gross_pnl"
    ]

    # Strategy B: profile + underreaction regime
    trade_df["signal_profile_regime"] = "skip"
    mask_profile_regime = (
        (trade_df["profile"] == "recovery")
        & (trade_df["regime"] == "underreaction")
    )
    trade_df.loc[mask_profile_regime, "signal_profile_regime"] = "long"

    trade_df["return_profile_regime"] = 0.0
    trade_df["pnl_profile_regime"] = 0.0
    trade_df.loc[mask_profile_regime, "return_profile_regime"] = trade_df.loc[
        mask_profile_regime, "gross_return_pct"
    ]
    trade_df.loc[mask_profile_regime, "pnl_profile_regime"] = trade_df.loc[
        mask_profile_regime, "gross_pnl"
    ]

    return trade_df


def summarize_strategy(
    df: pd.DataFrame,
    signal_col: str,
    return_col: str,
    pnl_col: str,
    label: str,
) -> None:
    traded = df[df[signal_col] != "skip"].copy()

    print(f"\n=== {label} ===")
    print(f"Rows in period:        {len(df)}")
    print(f"Trades taken:          {len(traded)}")

    if traded.empty:
        print("No trades taken.")
        return

    wins = (traded[pnl_col] > 0).sum()
    losses = (traded[pnl_col] <= 0).sum()
    avg_ret = traded[return_col].mean()
    med_ret = traded[return_col].median()
    total_pnl = traded[pnl_col].sum()
    win_rate = wins / len(traded) * 100.0

    print(f"Wins:                  {wins}")
    print(f"Losses:                {losses}")
    print(f"Win rate:              {win_rate:.2f}%")
    print(f"Average return:        {avg_ret:.4f}%")
    print(f"Median return:         {med_ret:.4f}%")
    print(f"Total strategy PnL:    ${total_pnl:,.2f}")

    print("\nBy ticker:")
    by_ticker = (
        traded.groupby("ticker")
        .agg(
            trades=("ticker", "count"),
            avg_return_pct=(return_col, "mean"),
            total_pnl=(pnl_col, "sum"),
            win_rate_pct=(pnl_col, lambda s: (s > 0).mean() * 100.0),
        )
        .sort_values("total_pnl", ascending=False)
        .round(4)
    )
    print(by_ticker.to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="Long-only recovery backtest")
    parser.add_argument("--outputs-dir", default="../outputs")
    parser.add_argument("--train-end", default="2021-12-31")
    parser.add_argument("--test-start", default="2022-01-01")
    parser.add_argument("--trade-hold", type=int, default=1)
    parser.add_argument("--regime-hold", type=int, default=1)
    parser.add_argument("--rolling-window", type=int, default=8)
    parser.add_argument("--overreaction-threshold", type=float, default=1.1)
    parser.add_argument("--underreaction-threshold", type=float, default=0.9)
    parser.add_argument("--min-avg-return", type=float, default=0.0)
    parser.add_argument("--min-win-rate", type=float, default=0.50)
    parser.add_argument("--output-dir", required=True, help="Directory where results will be saved",)
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    df = load_results(outputs_dir)

    train_end = pd.Timestamp(args.train_end)
    test_start = pd.Timestamp(args.test_start)

    df_train = df[df["ex_date"] <= train_end].copy()
    df_test = df[df["ex_date"] >= test_start].copy()

    profile_df = label_recovery_profiles(
        df_train=df_train,
        holds=(1, 3),
        min_avg_return=args.min_avg_return,
        min_win_rate=args.min_win_rate,
    )

    regime_df = build_regime_series(
        df=df,
        hold_for_regime=args.regime_hold,
        rolling_window=args.rolling_window,
        overreaction_threshold=args.overreaction_threshold,
        underreaction_threshold=args.underreaction_threshold,
    )

    print("\n=== TRAINED RECOVERY PROFILES ===")
    print(profile_df.to_string(index=False))

    strategy_df = apply_long_only_strategy(
        df_test=df_test,
        profile_df=profile_df,
        regime_df=regime_df,
        trade_hold_days=args.trade_hold,
    )

    summarize_strategy(
        strategy_df,
        signal_col="signal_profile_only",
        return_col="return_profile_only",
        pnl_col="pnl_profile_only",
        label="TEST: PROFILE ONLY",
    )

    summarize_strategy(
        strategy_df,
        signal_col="signal_profile_regime",
        return_col="return_profile_regime",
        pnl_col="pnl_profile_regime",
        label="TEST: PROFILE + UNDERREACTION REGIME",
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    save_path = output_dir / "long_only_recovery_test_trades.csv"
    strategy_df.to_csv(save_path, index=False)
    print(f"\nSaved test trades to: {save_path}")

if __name__ == "__main__":
    main()
