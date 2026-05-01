import argparse

import pandas as pd
import yfinance as yf

from backtester.analytics.volatility import compute_garch_metrics
from backtester.decision.volatility_decision import add_volatility_decisions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test volatility decision logic on real market data."
    )
    parser.add_argument("ticker", nargs="?", default="SPY")
    parser.add_argument("--period", default="2y")
    parser.add_argument("--tail", type=int, default=25)

    args = parser.parse_args()

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)

    raw = yf.download(args.ticker, period=args.period, progress=False)

    if raw.empty:
        raise SystemExit(f"No data returned for ticker: {args.ticker}")

    df = compute_garch_metrics(raw["Close"])
    df = add_volatility_decisions(df)

    cols = [
        "garch_vol_annualized",
        "vol_zscore",
        "vol_percentile",
        "vol_regime",
        "vol_spike_flag",
        "decision_vol_regime",
        "risk_multiplier",
        "preferred_strategy",
        "allow_options",
        "allow_new_equity_positions",
    ]

    print(f"\n{args.ticker} volatility decision output\n")
    print(df[cols].tail(args.tail))


if __name__ == "__main__":
    main()
