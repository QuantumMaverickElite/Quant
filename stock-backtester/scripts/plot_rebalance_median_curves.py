from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


FREQS = ["D", "W", "B", "3W", "M", "6W", "Q"]


def find_curves_file(freq: str) -> Path | None:
    candidates = [
        Path(f"outputs/monte_carlo/rebalance_{freq}_curves/monte_carlo_equity_curves.csv"),
        Path(f"outputs/monte_carlo/rebalance_{freq}_1000/monte_carlo_equity_curves.csv"),
        Path(f"outputs/monte_carlo/rebalance_{freq}/monte_carlo_equity_curves.csv"),
    ]

    for path in candidates:
        if path.exists():
            return path

    return None


def main() -> None:
    out_dir = Path("outputs/research/rebalance_frequency")
    out_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 7))

    found = []

    for freq in FREQS:
        path = find_curves_file(freq)

        if path is None:
            print(f"Skipping {freq}: no equity curves file found.")
            continue

        df = pd.read_csv(path)
        df["date"] = pd.to_datetime(df["date"])

        strategy = df[df["curve_type"] == "market_state"].copy()

        if strategy.empty:
            print(f"Skipping {freq}: no market_state curves found.")
            continue

        curve_matrix = strategy.pivot_table(
            index="date",
            columns="run_id",
            values="equity",
            aggfunc="last",
        ).sort_index()

        median_curve = curve_matrix.median(axis=1)

        ax.plot(
            median_curve.index,
            median_curve.values,
            linewidth=2.2,
            label=freq,
        )

        found.append(freq)

    ax.axhline(
        10_000,
        linestyle=":",
        linewidth=1.5,
        label="Starting capital",
    )

    ax.set_title("Median Strategy Equity Curve by Rebalance Frequency")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.3)
    ax.legend(title="Rebalance")

    fig.tight_layout()

    out_path = out_dir / "median_strategy_curves_by_rebalance.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"Found frequencies: {', '.join(found)}")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
