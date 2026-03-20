#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import re

import matplotlib.pyplot as plt
import pandas as pd


def parse_hold_days(filename: str) -> int | None:
    name = filename.lower()
    patterns = [
        r"hold[-_](\d+)",
        r"results_hold_(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, name)
        if m:
            return int(m.group(1))
    return None


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_hold_results(outputs_dir: Path) -> pd.DataFrame:
    files = sorted(outputs_dir.glob("*.csv"))
    frames = []

    for f in files:
        hold_days = parse_hold_days(f.name)
        if hold_days is None:
            continue

        df = pd.read_csv(f)
        if "ex_date" not in df.columns:
            continue

        df["ex_date"] = pd.to_datetime(df["ex_date"])
        df["hold_days"] = hold_days
        df["source_file"] = f.name
        frames.append(df)

    if not frames:
        raise FileNotFoundError("No hold-result CSVs found in outputs directory.")

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["hold_days", "ex_date", "ticker"]).reset_index(drop=True)
    return out


def load_long_only_results(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None

    df = pd.read_csv(path)
    if "ex_date" in df.columns:
        df["ex_date"] = pd.to_datetime(df["ex_date"])
    return df


def plot_avg_return_by_hold(df: pd.DataFrame, outdir: Path) -> None:
    s = df.groupby("hold_days")["gross_return_pct"].mean().sort_index()

    plt.figure(figsize=(8, 5))
    plt.plot(s.index, s.values, marker="o")
    plt.xlabel("Hold days")
    plt.ylabel("Average return (%)")
    plt.title("Average Return by Holding Period")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / "avg_return_by_hold.png", dpi=160)
    plt.close()


def plot_total_pnl_by_hold(df: pd.DataFrame, outdir: Path) -> None:
    s = df.groupby("hold_days")["gross_pnl"].sum().sort_index()

    plt.figure(figsize=(8, 5))
    plt.plot(s.index, s.values, marker="o")
    plt.xlabel("Hold days")
    plt.ylabel("Total gross PnL ($)")
    plt.title("Total Gross PnL by Holding Period")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / "total_pnl_by_hold.png", dpi=160)
    plt.close()


def plot_heatmap_returns(df: pd.DataFrame, outdir: Path) -> None:
    pivot = (
        df.groupby(["ticker", "hold_days"])["gross_return_pct"]
        .mean()
        .unstack("hold_days")
        .sort_index()
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(pivot.values, aspect="auto")

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)

    ax.set_xlabel("Hold days")
    ax.set_ylabel("Ticker")
    ax.set_title("Average Return (%) by Ticker and Hold Period")

    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.iloc[i, j]
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8)

    fig.colorbar(im, ax=ax, label="Avg return (%)")
    plt.tight_layout()
    plt.savefig(outdir / "ticker_hold_heatmap.png", dpi=160)
    plt.close()


def plot_cumulative_pnl_by_hold(df: pd.DataFrame, outdir: Path) -> None:
    for hold in sorted(df["hold_days"].unique()):
        sub = (
            df[df["hold_days"] == hold]
            .groupby("ex_date", as_index=True)["gross_pnl"]
            .sum()
            .sort_index()
        )
        cum = sub.cumsum()

        plt.figure(figsize=(10, 5))
        plt.plot(cum.index, cum.values)
        plt.xlabel("Ex-dividend date")
        plt.ylabel("Cumulative gross PnL ($)")
        plt.title(f"Cumulative Gross PnL Over Time (hold={hold})")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(outdir / f"cumulative_pnl_hold_{hold}.png", dpi=160)
        plt.close()


def plot_drop_ratio_over_time(df: pd.DataFrame, outdir: Path, rolling_window: int = 8) -> None:
    s = (
        df[df["hold_days"] == 1]
        .groupby("ex_date")["drop_ratio"]
        .mean()
        .sort_index()
        .rolling(rolling_window, min_periods=1)
        .mean()
    )

    plt.figure(figsize=(10, 5))
    plt.plot(s.index, s.values)
    plt.axhline(1.0, linestyle="--")
    plt.xlabel("Ex-dividend date")
    plt.ylabel("Rolling mean drop ratio")
    plt.title(f"Drop Ratio Over Time ({rolling_window}-event rolling mean)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / "drop_ratio_over_time.png", dpi=160)
    plt.close()


def plot_selected_ticker_cumulative(
    df: pd.DataFrame,
    outdir: Path,
    tickers: list[str],
    hold_days: int = 1,
) -> None:
    sub = df[(df["ticker"].isin(tickers)) & (df["hold_days"] == hold_days)].copy()
    if sub.empty:
        return

    plt.figure(figsize=(10, 5))

    for ticker in tickers:
        s = (
            sub[sub["ticker"] == ticker]
            .groupby("ex_date")["gross_pnl"]
            .sum()
            .sort_index()
            .cumsum()
        )
        if not s.empty:
            plt.plot(s.index, s.values, label=ticker)

    plt.xlabel("Ex-dividend date")
    plt.ylabel("Cumulative gross PnL ($)")
    plt.title(f"Cumulative PnL by Ticker (hold={hold_days})")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / f"selected_tickers_cumulative_hold_{hold_days}.png", dpi=160)
    plt.close()


def plot_selected_ticker_bar(
    df: pd.DataFrame,
    outdir: Path,
    tickers: list[str],
    hold_days: int = 1,
) -> None:
    sub = df[(df["ticker"].isin(tickers)) & (df["hold_days"] == hold_days)].copy()
    if sub.empty:
        return

    s = sub.groupby("ticker")["gross_return_pct"].mean().reindex(tickers)

    plt.figure(figsize=(8, 5))
    plt.bar(s.index, s.values)
    plt.xlabel("Ticker")
    plt.ylabel("Average return (%)")
    plt.title(f"Average Return for Selected Tickers (hold={hold_days})")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / f"selected_tickers_avg_return_hold_{hold_days}.png", dpi=160)
    plt.close()


def plot_long_only_equity_curve(df: pd.DataFrame, outdir: Path) -> None:
    needed = {"ex_date", "signal_profile_only", "pnl_profile_only", "signal_profile_regime", "pnl_profile_regime"}
    if not needed.issubset(df.columns):
        return

    profile_only = (
        df[df["signal_profile_only"] != "skip"]
        .groupby("ex_date")["pnl_profile_only"]
        .sum()
        .sort_index()
        .cumsum()
    )

    profile_regime = (
        df[df["signal_profile_regime"] != "skip"]
        .groupby("ex_date")["pnl_profile_regime"]
        .sum()
        .sort_index()
        .cumsum()
    )

    plt.figure(figsize=(10, 5))
    if not profile_only.empty:
        plt.plot(profile_only.index, profile_only.values, label="Profile only")
    if not profile_regime.empty:
        plt.plot(profile_regime.index, profile_regime.values, label="Profile + regime")
    plt.xlabel("Ex-dividend date")
    plt.ylabel("Cumulative strategy PnL ($)")
    plt.title("Long-Only Recovery Strategy Equity Curves")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / "long_only_equity_curves.png", dpi=160)
    plt.close()


def plot_long_only_ticker_contributions(df: pd.DataFrame, outdir: Path) -> None:
    needed = {"ticker", "signal_profile_only", "pnl_profile_only"}
    if not needed.issubset(df.columns):
        return

    s = (
        df[df["signal_profile_only"] != "skip"]
        .groupby("ticker")["pnl_profile_only"]
        .sum()
        .sort_values(ascending=False)
    )

    if s.empty:
        return

    plt.figure(figsize=(8, 5))
    plt.bar(s.index, s.values)
    plt.xlabel("Ticker")
    plt.ylabel("Total strategy PnL ($)")
    plt.title("Long-Only Recovery Strategy: PnL by Ticker")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / "long_only_ticker_contributions.png", dpi=160)
    plt.close()


def plot_long_only_trade_distribution(df: pd.DataFrame, outdir: Path) -> None:
    if "signal_profile_only" not in df.columns or "return_profile_only" not in df.columns:
        return

    s = df.loc[df["signal_profile_only"] != "skip", "return_profile_only"].dropna()
    if s.empty:
        return

    plt.figure(figsize=(8, 5))
    plt.hist(s, bins=20)
    plt.xlabel("Trade return (%)")
    plt.ylabel("Count")
    plt.title("Distribution of Long-Only Recovery Trade Returns")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / "long_only_trade_return_distribution.png", dpi=160)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Matplotlib visualizations for dividend capture research")
    parser.add_argument("--outputs-dir", default="../outputs", help="Directory with CSV outputs")
    parser.add_argument("--plot-dir", default="../outputs/plots_v2", help="Directory to save plots")
    parser.add_argument(
        "--long-only-file",
        default="../outputs/long_only_recovery_test_trades.csv",
        help="CSV from long_only_recovery_backtest.py",
    )
    parser.add_argument(
        "--selected-tickers",
        nargs="*",
        default=["PG", "PEP", "KO", "XOM", "VZ", "CVX"],
        help="Tickers to highlight in selected plots",
    )
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    plot_dir = Path(args.plot_dir)
    ensure_dir(plot_dir)

    hold_df = load_hold_results(outputs_dir)

    plot_avg_return_by_hold(hold_df, plot_dir)
    plot_total_pnl_by_hold(hold_df, plot_dir)
    plot_heatmap_returns(hold_df, plot_dir)
    plot_cumulative_pnl_by_hold(hold_df, plot_dir)
    plot_drop_ratio_over_time(hold_df, plot_dir, rolling_window=8)
    plot_selected_ticker_cumulative(hold_df, plot_dir, args.selected_tickers, hold_days=1)
    plot_selected_ticker_bar(hold_df, plot_dir, args.selected_tickers, hold_days=1)

    long_only_path = Path(args.long_only_file)
    long_only_df = load_long_only_results(long_only_path)
    if long_only_df is not None:
        plot_long_only_equity_curve(long_only_df, plot_dir)
        plot_long_only_ticker_contributions(long_only_df, plot_dir)
        plot_long_only_trade_distribution(long_only_df, plot_dir)

    print(f"Saved plots to: {plot_dir}")


if __name__ == "__main__":
    main()
