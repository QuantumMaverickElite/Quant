from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_equity(strategy_eq: pd.Series, bh_eq: pd.Series, ticker: str) -> str:
    Path("outputs").mkdir(exist_ok=True)

    plt.figure(figsize=(10, 6))
    plt.plot(strategy_eq.index, strategy_eq.values, label="Strategy")
    plt.plot(bh_eq.index, bh_eq.values, label="Buy & Hold", alpha=0.7)
    plt.title(f"Equity Curve — {ticker}")
    plt.xlabel("Date")
    plt.ylabel("Growth of $1")
    plt.grid(True)
    plt.legend()

    out_path = Path("outputs") / f"{ticker}_equity_curve.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()

    return str(out_path)

