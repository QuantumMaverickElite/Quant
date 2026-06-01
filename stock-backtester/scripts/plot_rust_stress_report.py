# scripts/plot_rust_stress_report.py

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot Rust stress test outputs.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out-dir", default=None)
    return parser.parse_args()


def save_bar(df: pd.DataFrame, x: str, y: str, title: str, out: Path) -> None:
    plt.figure(figsize=(12, 6))
    plt.bar(df[x].astype(str), df[y])
    plt.title(title)
    plt.xlabel(x)
    plt.ylabel(y)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def save_equity_curve(equity: pd.DataFrame, out: Path) -> None:
    plt.figure(figsize=(12, 6))
    plt.plot(pd.to_datetime(equity["date"]), equity["equity"])
    plt.title("Actual Equity Curve")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def save_drawdown_curve(equity: pd.DataFrame, out: Path) -> None:
    plt.figure(figsize=(12, 6))
    plt.plot(pd.to_datetime(equity["date"]), equity["drawdown"])
    plt.title("Actual Drawdown Curve")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def save_mc_summary(summary: pd.DataFrame, out: Path) -> None:
    cols = [
        "mc_median_total_return",
        "mc_p05_total_return",
        "mc_p95_total_return",
        "actual_total_return",
    ]

    plot_df = summary.set_index("test")[cols]

    plt.figure(figsize=(12, 6))
    plot_df.plot(kind="bar", ax=plt.gca())
    plt.title("Monte Carlo Return Distribution Summary")
    plt.xlabel("Test")
    plt.ylabel("Total Return")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def save_prob_beats(summary: pd.DataFrame, out: Path) -> None:
    plt.figure(figsize=(12, 6))
    plt.bar(summary["test"], summary["prob_random_beats_actual"])
    plt.title("Probability Random Control Beats Actual")
    plt.xlabel("Test")
    plt.ylabel("Probability")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def main() -> None:
    args = parse_args()

    run_dir = Path(args.run_dir)
    out_dir = Path(args.out_dir) if args.out_dir else run_dir / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)

    equity_path = run_dir / "actual_equity.csv"
    mc_summary_path = run_dir / "monte_carlo_summary.csv"
    selected_summary_path = run_dir / "selected_ticker_exclusion_summary.csv"
    sweep_path = run_dir / "sweep_summary.csv"
    ticker_exclusion_path = run_dir / "ticker_exclusion_summary.csv"
    year_exclusion_path = run_dir / "year_exclusion_summary.csv"
    top_winner_path = run_dir / "top_winner_exclusion_summary.csv"

    made = []

    if equity_path.exists():
        equity = pd.read_csv(equity_path)
        save_equity_curve(equity, out_dir / "equity_curve.png")
        save_drawdown_curve(equity, out_dir / "drawdown_curve.png")
        made += ["equity_curve.png", "drawdown_curve.png"]

    if mc_summary_path.exists():
        summary = pd.read_csv(mc_summary_path)
        save_mc_summary(summary, out_dir / "monte_carlo_summary.png")
        save_prob_beats(summary, out_dir / "prob_random_beats_actual.png")
        made += ["monte_carlo_summary.png", "prob_random_beats_actual.png"]

    if selected_summary_path.exists():
        summary = pd.read_csv(selected_summary_path)
        save_mc_summary(summary, out_dir / "selected_ticker_exclusion_summary.png")
        save_prob_beats(summary, out_dir / "selected_prob_random_beats_actual.png")
        made += [
            "selected_ticker_exclusion_summary.png",
            "selected_prob_random_beats_actual.png",
        ]

    if sweep_path.exists():
        sweep = pd.read_csv(sweep_path).head(20).copy()
        sweep["config"] = (
            "g="
            + sweep["max_gross_exposure"].astype(str)
            + ", b="
            + sweep["target_new_basket_exposure"].astype(str)
            + ", p="
            + sweep["max_position_weight"].astype(str)
        )
        save_bar(
            sweep,
            "config",
            "sharpe_like",
            "Top Sweep Configs by Sharpe-like Score",
            out_dir / "sweep_top_sharpe.png",
        )
        save_bar(
            sweep,
            "config",
            "total_return",
            "Top Sweep Configs by Total Return",
            out_dir / "sweep_top_return.png",
        )
        made += ["sweep_top_sharpe.png", "sweep_top_return.png"]

    if ticker_exclusion_path.exists():
        ex = pd.read_csv(ticker_exclusion_path).copy()
        worst = ex.sort_values("total_return").head(20)
        save_bar(
            worst,
            "excluded",
            "total_return",
            "Worst Ticker Exclusions by Return",
            out_dir / "ticker_exclusion_worst.png",
        )
        made += ["ticker_exclusion_worst.png"]

    if year_exclusion_path.exists():
        ex = pd.read_csv(year_exclusion_path).copy()
        save_bar(
            ex.sort_values("excluded"),
            "excluded",
            "total_return",
            "Year Exclusion Total Return",
            out_dir / "year_exclusion_return.png",
        )
        made += ["year_exclusion_return.png"]

    if top_winner_path.exists():
        tw = pd.read_csv(top_winner_path).copy()
        save_bar(
            tw,
            "excluded_top_n",
            "total_return",
            "Top Winner Exclusion Return",
            out_dir / "top_winner_exclusion_return.png",
        )
        save_bar(
            tw,
            "excluded_top_n",
            "sharpe_like",
            "Top Winner Exclusion Sharpe-like",
            out_dir / "top_winner_exclusion_sharpe.png",
        )
        made += ["top_winner_exclusion_return.png", "top_winner_exclusion_sharpe.png"]

    print(f"Saved plots to: {out_dir}")
    for name in made:
        print(f"- {name}")


if __name__ == "__main__":
    main()
