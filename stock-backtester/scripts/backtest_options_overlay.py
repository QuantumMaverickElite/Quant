import argparse
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

from backtester.engines.options_overlay_engine import run_options_overlay


def compute_buy_and_hold_returns(close: pd.Series) -> pd.Series:
    returns = close.pct_change().fillna(0.0)
    returns.name = "buy_hold_return"
    return returns


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backtest simplified options overlay strategy."
    )
    parser.add_argument("ticker", nargs="?", default="SPY")
    parser.add_argument("--period", default="5y")

    args = parser.parse_args()

    ticker = args.ticker.upper()

    raw = yf.download(
        ticker,
        period=args.period,
        auto_adjust=True,
        progress=False,
    )

    if raw.empty:
        raise SystemExit(f"No data returned for ticker: {ticker}")

    close = raw["Close"].squeeze().dropna()

    overlay = run_options_overlay(close)

    bh_returns = compute_buy_and_hold_returns(close)
    bh_returns = bh_returns.reindex(overlay.returns.index).fillna(0.0)
    bh_equity = (1.0 + bh_returns).cumprod()
    bh_equity.name = "buy_hold_equity"

    out = overlay.diagnostics.copy()
    out["buy_hold_return"] = bh_returns
    out["buy_hold_equity"] = bh_equity

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("outputs/options_overlay") / ticker / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "options_overlay_backtest.csv"
    plot_path = out_dir / "options_overlay_equity_curve.png"

    out.to_csv(csv_path)

    plt.figure(figsize=(11, 6))
    plt.plot(out.index, out["options_overlay_equity"], label="Options Overlay")
    plt.plot(out.index, out["buy_hold_equity"], label=f"{ticker} Buy & Hold")
    plt.title(f"{ticker} Options Overlay vs Buy & Hold")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()

    print(f"\nTicker: {ticker}")
    print(f"Period: {args.period}")
    print("\nSignal counts:")
    print(overlay.signals.value_counts())

    print(f"\nFinal options overlay equity: {overlay.equity.iloc[-1]:.4f}")
    print(f"Final buy & hold equity:      {bh_equity.iloc[-1]:.4f}")

    print(f"\nSaved CSV  -> {csv_path}")
    print(f"Saved plot -> {plot_path}")


if __name__ == "__main__":
    main()
