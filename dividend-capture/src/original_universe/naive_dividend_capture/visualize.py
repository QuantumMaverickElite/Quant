#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def load_results(outputs_dir: Path) -> pd.DataFrame:
    files = sorted(outputs_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {outputs_dir}")

    frames = []
    for f in files:
        df = pd.read_csv(f)

        hold_days = None
        name = f.stem.lower()
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
        raise ValueError("CSV files found, but none matched expected hold-day naming.")

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["hold_days", "ex_date", "ticker"]).reset_index(drop=True)
    return out


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


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


def plot_ticker_heatmap_like_table(df: pd.DataFrame, outdir: Path) -> None:
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


def plot_cumulative_event_pnl(df: pd.DataFrame, outdir: Path) -> None:
    for hold in sorted(df["hold_days"].unique()):
        sub = (
            df[df["hold_days"] == hold]
            .sort_values("ex_date")
            .groupby("ex_date", as_index=True)["gross_pnl"]
            .sum()
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


def plot_drop_ratio_over_time(df: pd.DataFrame, outdir: Path) -> None:
    s = (
        df.groupby("ex_date")["drop_ratio"]
        .mean()
        .sort_index()
        .rolling(8, min_periods=1)
        .mean()
    )

    plt.figure(figsize=(10, 5))
    plt.plot(s.index, s.values)
    plt.xlabel("Ex-dividend date")
    plt.ylabel("Rolling mean drop ratio")
    plt.title("Drop Ratio Over Time (8-event rolling mean)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / "drop_ratio_over_time.png", dpi=160)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot dividend capture backtest results")
    parser.add_argument("--outputs-dir", default="outputs", help="Directory containing result CSVs")
    parser.add_argument("--plot-dir", default="outputs/plots", help="Directory to save plots")
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    plot_dir = Path(args.plot_dir)
    ensure_dir(plot_dir)

    df = load_results(outputs_dir)

    plot_avg_return_by_hold(df, plot_dir)
    plot_total_pnl_by_hold(df, plot_dir)
    plot_ticker_heatmap_like_table(df, plot_dir)
    plot_cumulative_event_pnl(df, plot_dir)
    plot_drop_ratio_over_time(df, plot_dir)

    print(f"Saved plots to: {plot_dir}")


if __name__ == "__main__":
    main()
