# scripts/plot_rust_spaghetti.py

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot actual equity and drawdown curves from Rust stress outputs."
    )
    parser.add_argument("--run-dirs", nargs="+", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--title", default="Rust Stress Equity Curves")
    return parser.parse_args()


def clean_label(path: Path) -> str:
    name = path.name.removesuffix("_20k")
    name = name.replace("peer_spread_", "")
    name = name.replace("_v1", "")
    return name


def load_actual_equity(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "actual_equity.csv"
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    if "date" not in df.columns:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["date"])

    equity_col = None
    for col in ["equity", "portfolio_value", "final_equity", "total_equity"]:
        if col in df.columns:
            equity_col = col
            break

    if equity_col is None:
        numeric = [c for c in df.columns if c != "date" and pd.api.types.is_numeric_dtype(df[c])]
        if not numeric:
            return pd.DataFrame()
        equity_col = numeric[0]

    out = df[["date", equity_col]].copy()
    out.columns = ["date", "equity"]
    return out


def plot_equity_curves(run_dirs: list[Path], out_dir: Path, title: str, normalize: bool) -> None:
    plt.figure(figsize=(14, 8))

    plotted = 0
    for run_dir in run_dirs:
        df = load_actual_equity(run_dir)
        if df.empty:
            print(f"Skipping missing/empty actual equity: {run_dir}")
            continue

        y = df["equity"].astype(float)
        if normalize and len(y) and y.iloc[0] != 0:
            y = y / y.iloc[0]

        plt.plot(df["date"], y, linewidth=1.8, label=clean_label(run_dir))
        plotted += 1

    if plotted == 0:
        raise RuntimeError("No actual equity curves found.")

    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Normalized equity" if normalize else "Equity")
    plt.legend()
    plt.tight_layout()

    out_path = out_dir / ("actual_equity_curves_normalized.png" if normalize else "actual_equity_curves.png")
    plt.savefig(out_path, dpi=160)
    plt.close()
    print(f"Saved: {out_path}")


def plot_drawdown_curves(run_dirs: list[Path], out_dir: Path, title: str) -> None:
    plt.figure(figsize=(14, 8))

    plotted = 0
    for run_dir in run_dirs:
        df = load_actual_equity(run_dir)
        if df.empty:
            continue

        equity = df["equity"].astype(float)
        peak = equity.cummax()
        drawdown = equity / peak - 1.0

        plt.plot(df["date"], drawdown, linewidth=1.8, label=clean_label(run_dir))
        plotted += 1

    if plotted == 0:
        raise RuntimeError("No drawdown curves found.")

    plt.title(title + " Drawdowns")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.legend()
    plt.tight_layout()

    out_path = out_dir / "actual_drawdown_curves.png"
    plt.savefig(out_path, dpi=160)
    plt.close()
    print(f"Saved: {out_path}")


def main() -> None:
    args = parse_args()

    run_dirs = [Path(x) for x in args.run_dirs]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    plot_equity_curves(run_dirs, out_dir, args.title, normalize=False)
    plot_equity_curves(run_dirs, out_dir, args.title, normalize=True)
    plot_drawdown_curves(run_dirs, out_dir, args.title)


if __name__ == "__main__":
    main()
