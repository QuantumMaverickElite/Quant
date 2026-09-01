#!/usr/bin/env python3

import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def load_data(path):
    df = pd.read_csv(path)
    df["sell_date"] = pd.to_datetime(df["sell_date"])
    df = df.sort_values("sell_date")
    return df


def plot_equity_curve(df, plot_dir):
    df["cumulative_pnl"] = df["gross_pnl"].cumsum()

    plt.figure()
    plt.plot(df["sell_date"], df["cumulative_pnl"])
    plt.title("Long Only Recovery Strategy - Equity Curve")
    plt.xlabel("Date")
    plt.ylabel("Cumulative PnL")
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.savefig(plot_dir / "equity_curve.png")
    plt.close()


def plot_ticker_contributions(df, plot_dir):
    contrib = df.groupby("ticker")["gross_pnl"].sum().sort_values(ascending=False)

    plt.figure()
    contrib.plot(kind="bar")
    plt.title("PnL Contribution by Ticker")
    plt.ylabel("Total PnL")
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.savefig(plot_dir / "ticker_contributions.png")
    plt.close()


def plot_return_distribution(df, plot_dir):
    plt.figure()
    plt.hist(df["gross_return_pct"], bins=30)
    plt.title("Trade Return Distribution")
    plt.xlabel("Return (%)")
    plt.ylabel("Frequency")
    plt.tight_layout()

    plt.savefig(plot_dir / "return_distribution.png")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Visualize long-only recovery strategy results")
    parser.add_argument(
        "--input-file",
        required=True,
        help="CSV file with trades (long_only_recovery_test_trades.csv)",
    )
    parser.add_argument(
        "--plot-dir",
        required=True,
        help="Directory where plots will be saved",
    )
    args = parser.parse_args()

    df = load_data(args.input_file)

    plot_dir = Path(args.plot_dir)
    plot_dir.mkdir(parents=True, exist_ok=True)

    plot_equity_curve(df, plot_dir)
    plot_ticker_contributions(df, plot_dir)
    plot_return_distribution(df, plot_dir)

    print(f"Saved plots to: {plot_dir}")


if __name__ == "__main__":
    main()
