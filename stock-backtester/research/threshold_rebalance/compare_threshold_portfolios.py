from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


PORTS = [5, 8, 12]
BASE = Path("outputs/threshold_rebalance")


def load_summary(port: int) -> pd.DataFrame:
    path = BASE / f"weekly_check_sample24_port{port}_paired_curves_v1" / "threshold_summary.csv"

    if not path.exists():
        raise FileNotFoundError(f"Missing summary file: {path}")

    df = pd.read_csv(path)
    df["portfolio_size"] = port
    df["source"] = str(path)
    return df


def main() -> None:
    out_dir = Path("outputs/research/threshold_rebalance")
    out_dir.mkdir(parents=True, exist_ok=True)

    comparison = pd.concat([load_summary(port) for port in PORTS], ignore_index=True)

    comparison = comparison.sort_values(
        ["portfolio_size", "threshold"]
    ).reset_index(drop=True)

    csv_path = out_dir / "threshold_portfolio_comparison.csv"
    comparison.to_csv(csv_path, index=False)

    print("\nThreshold Portfolio Comparison")
    print("=" * 140)
    print(
        comparison[
            [
                "portfolio_size",
                "threshold",
                "mean_return_pct",
                "median_return_pct",
                "mean_sharpe",
                "median_sharpe",
                "mean_max_drawdown_pct",
                "prob_loss_pct",
                "prob_sharpe_below_1_pct",
                "mean_rebalances",
                "mean_turnover_pct",
            ]
        ].round(4).to_string(index=False)
    )
    print("=" * 140)
    print(f"Wrote: {csv_path}")

    best_by_return = comparison.loc[
        comparison.groupby("portfolio_size")["mean_return_pct"].idxmax()
    ].sort_values("portfolio_size")

    best_by_sharpe = comparison.loc[
        comparison.groupby("portfolio_size")["mean_sharpe"].idxmax()
    ].sort_values("portfolio_size")

    best_return_path = out_dir / "best_threshold_by_return.csv"
    best_sharpe_path = out_dir / "best_threshold_by_sharpe.csv"

    best_by_return.to_csv(best_return_path, index=False)
    best_by_sharpe.to_csv(best_sharpe_path, index=False)

    print("\nBest threshold by mean return")
    print("=" * 100)
    print(
        best_by_return[
            [
                "portfolio_size",
                "threshold",
                "mean_return_pct",
                "median_return_pct",
                "mean_sharpe",
                "mean_rebalances",
            ]
        ].round(4).to_string(index=False)
    )

    print("\nBest threshold by mean Sharpe")
    print("=" * 100)
    print(
        best_by_sharpe[
            [
                "portfolio_size",
                "threshold",
                "mean_return_pct",
                "median_return_pct",
                "mean_sharpe",
                "mean_rebalances",
            ]
        ].round(4).to_string(index=False)
    )

    print(f"\nWrote: {best_return_path}")
    print(f"Wrote: {best_sharpe_path}")

    charts = [
        ("mean_return_pct", "Mean Total Return (%)", "mean_return_by_threshold_portfolio.png"),
        ("median_return_pct", "Median Total Return (%)", "median_return_by_threshold_portfolio.png"),
        ("mean_sharpe", "Mean Sharpe", "mean_sharpe_by_threshold_portfolio.png"),
        ("mean_rebalances", "Mean Rebalances", "mean_rebalances_by_threshold_portfolio.png"),
        ("prob_sharpe_below_1_pct", "Probability Sharpe Below 1 (%)", "prob_sharpe_below_1_by_threshold_portfolio.png"),
        ("mean_max_drawdown_pct", "Mean Max Drawdown (%)", "mean_drawdown_by_threshold_portfolio.png"),
    ]

    for column, title, filename in charts:
        fig, ax = plt.subplots(figsize=(11, 7))

        for port in PORTS:
            sub = comparison[comparison["portfolio_size"] == port]
            ax.plot(
                sub["threshold"],
                sub[column],
                marker="o",
                linewidth=2.2,
                label=f"PORT={port}",
            )

        ax.set_title(title)
        ax.set_xlabel("Threshold")
        ax.set_ylabel(title)
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()

        chart_path = out_dir / filename
        fig.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        print(f"Wrote: {chart_path}")


if __name__ == "__main__":
    main()
