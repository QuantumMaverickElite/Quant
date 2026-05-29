from pathlib import Path
import argparse

import pandas as pd
import yfinance as yf

from backtester.analytics.entropy import EntropyConfig, compute_entropy_metrics
from backtester.decision.entropy_decision import (
    apply_entropy_decision_columns,
    latest_entropy_decision,
)
from backtester.visuals.entropy_plot import plot_price_and_entropy


def clean_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize yfinance columns so the rest of the entropy engine can reliably
    expect lowercase single-level columns like: close, open, high, low, volume.
    """
    out = df.copy()

    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)

    out.columns = [str(col).lower() for col in out.columns]
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute rolling Shannon entropy metrics for a stock ticker."
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
        help="Start date for price history. Default: 2018-01-01",
    )

    parser.add_argument(
        "--end",
        default=None,
        help="Optional end date for price history. Default: latest available data",
    )

    parser.add_argument(
        "--entropy-window",
        type=int,
        default=60,
        help="Rolling window used to compute return entropy. Default: 60",
    )

    parser.add_argument(
        "--zscore-window",
        type=int,
        default=252,
        help="Rolling window used for entropy z-score and percentile. Default: 252",
    )

    parser.add_argument(
        "--bins",
        type=int,
        default=10,
        help="Number of return bins used in Shannon entropy calculation. Default: 10",
    )

    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Run entropy calculations without saving a plot.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ticker = args.ticker.upper()

    print(f"\nRunning entropy engine for {ticker}")
    print(f"Start: {args.start}")
    print(f"End: {args.end if args.end else 'latest'}")
    print(f"Entropy window: {args.entropy_window}")
    print(f"Z-score window: {args.zscore_window}")
    print(f"Bins: {args.bins}")

    df = yf.download(
        ticker,
        start=args.start,
        end=args.end,
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        raise ValueError(f"No data returned for ticker {ticker}")

    df = clean_yfinance_columns(df)

    if "close" not in df.columns:
        raise ValueError(
            f"Expected a 'close' column after cleaning yfinance data. "
            f"Got columns: {list(df.columns)}"
        )

    config = EntropyConfig(
        price_col="close",
        entropy_window=args.entropy_window,
        zscore_window=args.zscore_window,
        n_bins=args.bins,
    )

    metrics = compute_entropy_metrics(df, config)
    metrics = apply_entropy_decision_columns(metrics)

    decision = latest_entropy_decision(metrics)

    print("\nLatest entropy decision:")
    print(decision)
    print("\nEntropy state description:")
    print(decision.entropy_state_description)

    print("\nTail:")
    cols = [
        "close",
        "normalized_entropy",
        "entropy_percentile",
        "entropy_regime",
        "normalized_direction_entropy",
        "direction_entropy_percentile",
        "direction_entropy_regime",
        "entropy_state",
        "signal_trust_multiplier",
    ]
    print(metrics[cols].tail(10))

    if not args.no_plot:
        output_path = Path("outputs") / "entropy" / ticker / "price_entropy.png"

        plot_price_and_entropy(
            metrics,
            ticker=ticker,
            output_path=output_path,
        )

        print(f"\nSaved plot to: {output_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
