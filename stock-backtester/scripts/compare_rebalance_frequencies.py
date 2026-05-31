from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


FREQS = ["D", "W", "B", "3W", "M", "6W", "Q"]


def find_result_dir(freq: str) -> Path | None:
    base = Path("outputs/monte_carlo")

    preferred = base / f"rebalance_{freq}_1000"
    fallback = base / f"rebalance_{freq}"

    if preferred.exists():
        return preferred

    if fallback.exists():
        return fallback

    return None


def get_distribution_metric(path: Path, metric: str, field: str = "mean") -> float | None:
    df = pd.read_csv(path / "monte_carlo_distribution.csv")
    row = df[df["metric"] == metric]

    if row.empty:
        return None

    return float(row.iloc[0][field])


def get_benchmark_metric(path: Path, metric: str, field: str = "mean") -> float | None:
    df = pd.read_csv(path / "monte_carlo_benchmark_comparison.csv")
    row = df[df["metric"] == metric]

    if row.empty:
        return None

    return float(row.iloc[0][field])


def get_risk_metric(path: Path, metric: str) -> float | None:
    df = pd.read_csv(path / "monte_carlo_risk_stats.csv")

    if df.empty or metric not in df.columns:
        return None

    return float(df.iloc[0][metric])


def main() -> None:
    rows = []

    for freq in FREQS:
        result_dir = find_result_dir(freq)

        if result_dir is None:
            print(f"Skipping {freq}: no result folder found.")
            continue

        rows.append(
            {
                "freq": freq,
                "result_dir": str(result_dir),
                "mean_return_pct": get_distribution_metric(result_dir, "total_return_pct", "mean"),
                "median_return_pct": get_distribution_metric(result_dir, "total_return_pct", "median"),
                "mean_cagr_pct": get_distribution_metric(result_dir, "cagr_pct", "mean"),
                "mean_sharpe": get_distribution_metric(result_dir, "sharpe", "mean"),
                "median_sharpe": get_distribution_metric(result_dir, "sharpe", "median"),
                "mean_max_drawdown_pct": get_distribution_metric(result_dir, "max_drawdown_pct", "mean"),
                "prob_loss_pct": get_risk_metric(result_dir, "prob_loss_pct"),
                "prob_dd_worse_40_pct": get_risk_metric(result_dir, "prob_dd_worse_40_pct"),
                "prob_sharpe_below_1_pct": get_risk_metric(result_dir, "prob_sharpe_below_1_pct"),
                "excess_return_vs_ew_rebalance_pct": get_benchmark_metric(
                    result_dir,
                    "excess_return_vs_ew_rebalance_pct",
                    "mean",
                ),
                "excess_return_vs_ew_buy_hold_pct": get_benchmark_metric(
                    result_dir,
                    "excess_return_vs_ew_buy_hold_pct",
                    "mean",
                ),
                "beat_ew_rebalance_return_pct": get_benchmark_metric(
                    result_dir,
                    "beat_ew_rebalance_return_pct",
                    "mean",
                ),
                "beat_ew_buy_hold_return_pct": get_benchmark_metric(
                    result_dir,
                    "beat_ew_buy_hold_return_pct",
                    "mean",
                ),
            }
        )

    comparison = pd.DataFrame(rows)

    if comparison.empty:
        raise SystemExit("No rebalance results found.")

    order = {freq: i for i, freq in enumerate(FREQS)}
    comparison["_order"] = comparison["freq"].map(order)
    comparison = comparison.sort_values("_order").drop(columns=["_order"])

    out_dir = Path("outputs/research/rebalance_frequency")
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "rebalance_frequency_comparison.csv"
    comparison.to_csv(csv_path, index=False)

    print("\nRebalance Frequency Comparison")
    print("=" * 120)
    print(
        comparison[
            [
                "freq",
                "mean_return_pct",
                "median_return_pct",
                "mean_sharpe",
                "mean_max_drawdown_pct",
                "prob_loss_pct",
                "beat_ew_rebalance_return_pct",
                "beat_ew_buy_hold_return_pct",
            ]
        ].round(4).to_string(index=False)
    )
    print("=" * 120)
    print(f"Wrote: {csv_path}")

    charts = [
        ("mean_return_pct", "Mean Total Return (%)", "mean_return_pct.png"),
        ("median_return_pct", "Median Total Return (%)", "median_return_pct.png"),
        ("mean_sharpe", "Mean Sharpe", "mean_sharpe.png"),
        ("prob_loss_pct", "Probability of Loss (%)", "prob_loss_pct.png"),
        ("beat_ew_rebalance_return_pct", "Beat Equal-Weight Rebalance (%)", "beat_ew_rebalance_pct.png"),
        ("beat_ew_buy_hold_return_pct", "Beat Equal-Weight Buy-and-Hold (%)", "beat_ew_buy_hold_pct.png"),
    ]

    for column, title, filename in charts:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(comparison["freq"], comparison[column])
        ax.set_title(title)
        ax.set_xlabel("Rebalance Frequency")
        ax.set_ylabel(title)
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()

        chart_path = out_dir / filename
        fig.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        print(f"Wrote: {chart_path}")


if __name__ == "__main__":
    main()
