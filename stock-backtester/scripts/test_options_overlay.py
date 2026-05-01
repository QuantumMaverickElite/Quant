import argparse

import yfinance as yf

from backtester.engines.options_overlay_engine import run_options_overlay


def main() -> None:
    parser = argparse.ArgumentParser(description="Test options overlay engine.")
    parser.add_argument("ticker", nargs="?", default="SPY")
    parser.add_argument("--period", default="5y")
    parser.add_argument("--tail", type=int, default=30)

    args = parser.parse_args()

    raw = yf.download(args.ticker, period=args.period, auto_adjust=True, progress=False)

    if raw.empty:
        raise SystemExit(f"No data returned for ticker: {args.ticker}")

    close = raw["Close"].squeeze()

    result = run_options_overlay(close)

    out = result.diagnostics[
        [
            "price",
            "fast_vol",
            "slow_iv_proxy",
            "regime_mean",
            "options_signal",
            "options_overlay_return",
            "options_overlay_equity",
        ]
    ]

    print(f"\n{args.ticker.upper()} options overlay output\n")
    print(out.tail(args.tail))
    print("\nSignal counts:")
    print(result.signals.value_counts())


if __name__ == "__main__":
    main()
