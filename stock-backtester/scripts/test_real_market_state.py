from __future__ import annotations

import argparse

import pandas as pd
import yfinance as yf

from backtester.analytics.entropy import EntropyConfig, compute_entropy_metrics
from backtester.decision.entropy_decision import (
    apply_entropy_decision_columns,
    latest_entropy_decision,
)
from backtester.decision.market_state import build_market_state
from backtester.decision.volatility_decision import (
    add_volatility_decisions,
    make_volatility_decision,
)


def import_compute_garch_metrics():
    """
    Import the existing GARCH metric function.

    If your project's GARCH file uses a different module name, add it here.
    """
    try:
        from backtester.analytics.garch import compute_garch_metrics

        return compute_garch_metrics
    except ImportError:
        pass

    try:
        from backtester.analytics.garch_metrics import compute_garch_metrics

        return compute_garch_metrics
    except ImportError:
        pass

    try:
        from backtester.analytics.volatility import compute_garch_metrics

        return compute_garch_metrics
    except ImportError:
        pass

    raise ImportError(
        "Could not import compute_garch_metrics. "
        "Check the filename in src/backtester/analytics/ and update "
        "import_compute_garch_metrics() in this script."
    )


def clean_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)

    out.columns = [str(col).lower() for col in out.columns]
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build real MarketState from entropy + real volatility decision."
    )

    parser.add_argument(
        "--ticker",
        "-t",
        default="SPY",
        help="Ticker symbol to analyze. Default: SPY",
    )

    parser.add_argument(
        "--start",
        default="2018-01-01",
        help="Start date. Default: 2018-01-01",
    )

    parser.add_argument(
        "--end",
        default=None,
        help="Optional end date. Default: latest available data",
    )

    parser.add_argument(
        "--entropy-window",
        type=int,
        default=60,
        help="Rolling entropy window. Default: 60",
    )

    parser.add_argument(
        "--zscore-window",
        type=int,
        default=252,
        help="Rolling entropy z-score / percentile window. Default: 252",
    )

    parser.add_argument(
        "--bins",
        type=int,
        default=10,
        help="Number of bins for return entropy. Default: 10",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ticker = args.ticker.upper()

    print(f"\nRunning real MarketState test for {ticker}")
    print(f"Start: {args.start}")
    print(f"End: {args.end if args.end else 'latest'}")

    df = yf.download(
        ticker,
        start=args.start,
        end=args.end,
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        raise ValueError(f"No data returned for ticker {ticker}")

    prices = clean_yfinance_columns(df)

    if "close" not in prices.columns:
        raise ValueError(f"Missing close column. Got columns: {list(prices.columns)}")

    # ------------------------------------------------------------
    # 1. Real volatility decision
    # ------------------------------------------------------------
    compute_garch_metrics = import_compute_garch_metrics()

    vol_price_series = prices[["close"]].copy()
    vol_metrics = compute_garch_metrics(vol_price_series)

    if vol_metrics.empty:
        raise ValueError("GARCH volatility metrics returned an empty DataFrame.")

    vol_metrics = add_volatility_decisions(vol_metrics)

    latest_vol_row = vol_metrics.dropna().iloc[-1]
    volatility_decision = make_volatility_decision(latest_vol_row)

    # ------------------------------------------------------------
    # 2. Entropy decision
    # ------------------------------------------------------------
    entropy_config = EntropyConfig(
        price_col="close",
        entropy_window=args.entropy_window,
        zscore_window=args.zscore_window,
        n_bins=args.bins,
    )

    entropy_metrics = compute_entropy_metrics(prices, entropy_config)
    entropy_metrics = apply_entropy_decision_columns(entropy_metrics)

    entropy_decision = latest_entropy_decision(entropy_metrics)

    # ------------------------------------------------------------
    # 3. Combined market state
    # ------------------------------------------------------------
    market_state = build_market_state(
        entropy_decision=entropy_decision,
        volatility_decision=volatility_decision,
    )

    print("\nVolatility decision:")
    print(volatility_decision)

    print("\nEntropy decision:")
    print(entropy_decision)

    print("\nEntropy state description:")
    print(entropy_decision.entropy_state_description)

    print("\nMarket state:")
    print(market_state)

    print("\nMarket state reason:")
    print(market_state.reason)

    print("\nLatest volatility row:")
    vol_cols = [
        col
        for col in [
            "garch_vol",
            "vol_zscore",
            "vol_percentile",
            "vol_spike_flag",
            "vol_regime",
            "decision_vol_regime",
            "risk_multiplier",
            "allow_options",
            "allow_new_equity_positions",
        ]
        if col in vol_metrics.columns
    ]
    print(vol_metrics[vol_cols].tail(5))

    print("\nLatest entropy rows:")
    entropy_cols = [
        "close",
        "entropy_regime",
        "direction_entropy_regime",
        "entropy_state",
        "signal_trust_multiplier",
    ]
    print(entropy_metrics[entropy_cols].tail(5))

    print("\nDone.")


if __name__ == "__main__":
    main()
