# scripts/run_peer_spread_features.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

from backtester.correlation.spreads import compute_peer_spread_features

DEFAULT_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "GOOGL",
    "META",
    "ORCL",
    "AMD",
    "JPM",
    "BAC",
    "WFC",
    "GS",
    "MS",
    "XOM",
    "CVX",
    "COP",
    "OXY",
    "WMT",
    "COST",
    "TGT",
    "HD",
    "LOW",
    "JNJ",
    "PFE",
    "MRK",
    "ABBV",
    "LLY",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate peer-relative spread features for mean reversion."
    )

    parser.add_argument(
        "--features",
        default="outputs/correlation/features.parquet",
        help="Correlation feature parquet file.",
    )
    parser.add_argument(
        "--out",
        default="outputs/correlation/peer_spreads.parquet",
        help="Output peer spread feature parquet file.",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Ticker universe.",
    )
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument(
        "--horizons",
        nargs="+",
        type=int,
        default=[5, 20],
        help="Trailing return horizons.",
    )
    parser.add_argument(
        "--z-window",
        type=int,
        default=60,
        help="Rolling z-score window measured in feature rows.",
    )
    parser.add_argument(
        "--corr-window",
        type=int,
        default=None,
        help="Optional filter for one correlation window, e.g. 120.",
    )

    return parser.parse_args()


def download_adjusted_close(
    tickers: list[str],
    start: str,
    end: str | None,
) -> pd.DataFrame:
    data = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )

    if data.empty:
        raise RuntimeError("No price data downloaded.")

    if isinstance(data.columns, pd.MultiIndex):
        if "Close" not in data.columns.get_level_values(0):
            raise RuntimeError("Downloaded data does not contain Close prices.")

        close = data["Close"]
    else:
        if "Close" not in data.columns:
            raise RuntimeError("Downloaded data does not contain Close prices.")

        close = data[["Close"]]
        close.columns = tickers

    close.index = pd.to_datetime(close.index)
    return close.sort_index()


def main() -> None:
    args = parse_args()

    feature_path = Path(args.features)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not feature_path.exists():
        raise FileNotFoundError(f"Correlation feature file not found: {feature_path}")

    tickers = list(dict.fromkeys(args.tickers))

    corr_features = pd.read_parquet(feature_path)

    if args.corr_window is not None:
        corr_features = corr_features[
            corr_features["window"] == args.corr_window
        ].copy()

        if corr_features.empty:
            raise RuntimeError(
                f"No correlation features found for window={args.corr_window}"
            )

    prices = download_adjusted_close(
        tickers=tickers,
        start=args.start,
        end=args.end,
    )

    spreads = compute_peer_spread_features(
        prices=prices,
        correlation_features=corr_features,
        horizons=tuple(args.horizons),
        z_window=args.z_window,
    )

    spreads.to_parquet(out_path, index=False)

    print(f"Saved {len(spreads):,} rows to {out_path}")
    print(spreads.tail(20).to_string(index=False))


if __name__ == "__main__":
    main()
