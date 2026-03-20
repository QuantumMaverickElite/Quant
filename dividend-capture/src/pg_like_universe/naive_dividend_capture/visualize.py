#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
import re

import matplotlib.pyplot as plt
import pandas as pd


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def parse_hold_days(filename: str) -> int | None:
    name = filename.lower()
    patterns = [
        r"pg_like_hold_(\d+)",
        r"hold[-_](\d+)",
        r"results_hold_(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, name)
        if m:
            return int(m.group(1))
    return None


def load_pg_like_results(outputs_dir: Path) -> pd.DataFrame:
    files = sorted(outputs_dir.glob("hold_*.csv"))
    if not files:
        raise FileNotFoundError(f"No hold_*.csv files found in {outputs_dir}")

    frames = []
    for f in files:
        hold_days = parse_hold_days(f.name)
        if hold_days is None:
            continue

        df = pd.read_csv(f)
        df["ex_date"] = pd.to_datetime(df["ex_date"])
        df["hold_days"] = hold_days
        df["source_file"] = f.name
        frames.append(df)

    if not frames:
        raise ValueError("No valid PG-like hold files were loaded.")

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["hold_days", "ex_date", "ticker"]).reset_index(drop=True)
    return out


def plot_avg_return_by_hold(df: pd.DataFrame, outdir: Path) -> None:
    s = df.groupby("hold_days")["gross_return_pct"].mean().sort_index()

    plt.figure(figsize=(8, 5))
    plt.plot(s.index, s.values, marker="o")
    plt.xlabel("Hold days")
    plt.ylabel("Average return (%)")
    plt.title("PG-like Universe: Average Return by Hold")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / "pg_like_avg_return_by_hold.png", dpi=160)
    plt.close()


def plot_total_pnl_by_hold(df: pd.DataFrame, outdir: Path) -> None:
    s = df.groupby("hold_days")["gross_pnl"].sum().sort_index()

    plt.figure(figsize=(8, 5))
    plt.plot(s.index, s.values, marker="o")
    plt.xlabel("Hold days")
    plt.ylabel("Total gross PnL ($)")
    plt.title("PG-like Universe: Total Gross PnL by Hold")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / "pg_like_total_pnl_by_hold.png", dpi=160)
    plt.close()


def plot_heatmap(df: pd.DataFrame, outdir: Path) -> None:
    pivot = (
        df.groupby(["ticker", "hold_days"])["gross_return_pct"]
        .mean()
        .unstack("hold_days")
        .sort_index()
    )

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(pivot.values, aspect="auto")

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)

    ax.set_xlabel("Hold days")
    ax.set_ylabel("Ticker")
    ax.set_title("PG-like Universe: Avg Return (%) by Ticker and Hold")

    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.iloc[i, j]
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8)

    fig.colorbar(im, ax=ax, label="Avg return (%)")
    plt.tight_layout()
    plt.savefig(outdir / "pg_like_ticker_hold_heatmap.png", dpi=160)
    plt.close()


def plot_cumulative_pnl_by_hold(df: pd.DataFrame, outdir: Path) -> None:
    for hold in sorted(df["hold_days"].unique()):
        s = (
            df[df["hold_days"] == hold]
            .groupby("ex_date")["gross_pnl"]
            .sum()
            .sort_index()
            .cumsum()
        )

        plt.figure(figsize=(10, 5))
        plt.plot(s.index, s.values)
        plt.xlabel("Ex-dividend date")
        plt.ylabel("Cumulative gross PnL ($)")
        plt.title(f"PG-like Universe: Cumulative PnL (hold={hold})")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(outdir / f"pg_like_cumulative_pnl_hold_{hold}.png", dpi=160)
        plt.close()


def plot_per_ticker_equity(df: pd.DataFrame, outdir: Path, hold_days: int) -> None:
    sub = df[df["hold_days"] == hold_days].copy()
    if sub.empty:
        return

    plt.figure(figsize=(11, 6))

    for ticker in sorted(sub["ticker"].unique()):
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
    plt.title(f"PG-like Universe: Per-Ticker Equity Curves (hold={hold_days})")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(outdir / f"pg_like_per_ticker_equity_hold_{hold_days}.png", dpi=160)
    plt.close()


def plot_ticker_bar_by_hold(df: pd.DataFrame, outdir: Path, hold_days: int) -> None:
    sub = df[df["hold_days"] == hold_days].copy()
    if sub.empty:
        return

    s = sub.groupby("ticker")["gross_return_pct"].mean().sort_values(ascending=False)

    plt.figure(figsize=(9, 5))
    plt.bar(s.index, s.values)
    plt.xlabel("Ticker")
    plt.ylabel("Average return (%)")
    plt.title(f"PG-like Universe: Avg Return by Ticker (hold={hold_days})")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(outdir / f"pg_like_avg_return_by_ticker_hold_{hold_days}.png", dpi=160)
    plt.close()


def plot_best_hold_by_ticker(df: pd.DataFrame, outdir: Path) -> None:
    pivot = (
        df.groupby(["ticker", "hold_days"])["gross_return_pct"]
        .mean()
        .unstack("hold_days")
        .sort_index()
    )

    best_hold = pivot.idxmax(axis=1)
    best_val = pivot.max(axis=1)

    plt.figure(figsize=(9, 5))
    plt.bar(best_hold.index, best_val.values)
    plt.xlabel("Ticker")
    plt.ylabel("Best average return (%)")
    plt.title("PG-like Universe: Best Hold Period by Ticker")
    plt.grid(True, axis="y", alpha=0.3)

    for i, (ticker, hold) in enumerate(best_hold.items()):
        plt.text(i, best_val.loc[ticker], f"h={hold}", ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    plt.savefig(outdir / "pg_like_best_hold_by_ticker.png", dpi=160)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize PG-like dividend backtests")
    parser.add_argument("--outputs-dir", default="../outputs")
    parser.add_argument("--plot-dir", default="../outputs/plots_pg_like")
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    plot_dir = Path(args.plot_dir)
    ensure_dir(plot_dir)

    df = load_pg_like_results(outputs_dir)

    plot_avg_return_by_hold(df, plot_dir)
    plot_total_pnl_by_hold(df, plot_dir)
    plot_heatmap(df, plot_dir)
    plot_cumulative_pnl_by_hold(df, plot_dir)

    for hold in sorted(df["hold_days"].unique()):
        plot_per_ticker_equity(df, plot_dir, hold_days=hold)
        plot_ticker_bar_by_hold(df, plot_dir, hold_days=hold)

    plot_best_hold_by_ticker(df, plot_dir)

    print(f"Saved plots to: {plot_dir}")


if __name__ == "__main__":
    main()
