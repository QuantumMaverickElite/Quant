import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def load_equity(path: str, label: str) -> pd.Series:
    df = pd.read_csv(path, index_col=0, parse_dates=True)

    if "combined_equity" in df.columns:
        equity = df["combined_equity"]
    elif "equity" in df.columns:
        equity = df["equity"]
    else:
        raise ValueError(f"No equity column found in {path}")

    equity.name = label
    return equity


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare multiple regime backtest CSV files on one chart."
    )
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--router", required=True)
    parser.add_argument("--overlay", required=True)
    parser.add_argument("--ticker", default="TSLA")

    args = parser.parse_args()

    baseline = load_equity(args.baseline, "Baseline Regime")
    router = load_equity(args.router, "Router Regime")
    overlay = load_equity(args.overlay, "Router + Options Overlay")

    df = pd.concat([baseline, router, overlay], axis=1).dropna()

    out_dir = Path("outputs/comparisons") / args.ticker.upper()
    out_dir.mkdir(parents=True, exist_ok=True)

    out_csv = out_dir / "regime_comparison.csv"
    out_plot = out_dir / "regime_comparison.png"

    df.to_csv(out_csv)

    plt.figure(figsize=(12, 7))
    for col in df.columns:
        plt.plot(df.index, df[col], label=col)

    plt.title(f"{args.ticker.upper()} Regime Strategy Comparison")
    plt.xlabel("Date")
    plt.ylabel("Growth of $1")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_plot)
    plt.close()

    print(f"Saved CSV  -> {out_csv}")
    print(f"Saved plot -> {out_plot}")


if __name__ == "__main__":
    main()
