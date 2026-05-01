import argparse

import pandas as pd
import yfinance as yf

from backtester.analytics.volatility import compute_garch_metrics
from backtester.decision.regime_router import add_regime_routes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test market regime router on real market data."
    )
    parser.add_argument("ticker", nargs="?", default="SPY")
    parser.add_argument("--period", default="2y")
    parser.add_argument("--tail", type=int, default=25)

    args = parser.parse_args()

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 220)

    raw = yf.download(args.ticker, period=args.period, progress=False)

    if raw.empty:
        raise SystemExit(f"No data returned for ticker: {args.ticker}")

    df = compute_garch_metrics(raw["Close"])
    df = add_regime_routes(df)

    cols = [
        "vol_regime",
        "vol_zscore",
        "vol_percentile",
        "vol_spike_flag",
        "active_regime",
        "route_risk_multiplier",
        "route_preferred_strategy",
        "route_allow_options",
        "route_allow_new_equity_positions",
    ]

    print(f"\n{args.ticker.upper()} regime router output\n")
    print(df[cols].tail(args.tail))


if __name__ == "__main__":
    main()
