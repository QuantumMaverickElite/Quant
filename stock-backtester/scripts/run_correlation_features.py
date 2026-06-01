# scripts/run_correlation_features.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

from backtester.correlation import (
    CorrelationTracker,
    CorrelationTrackerConfig,
    build_asset_metadata,
    prices_to_return_matrix,
)

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


DEFAULT_SECTORS = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "GOOGL": "Communication Services",
    "META": "Communication Services",
    "ORCL": "Technology",
    "AMD": "Technology",
    "JPM": "Financial Services",
    "BAC": "Financial Services",
    "WFC": "Financial Services",
    "GS": "Financial Services",
    "MS": "Financial Services",
    "XOM": "Energy",
    "CVX": "Energy",
    "COP": "Energy",
    "OXY": "Energy",
    "WMT": "Consumer Defensive",
    "COST": "Consumer Defensive",
    "TGT": "Consumer Defensive",
    "HD": "Consumer Cyclical",
    "LOW": "Consumer Cyclical",
    "JNJ": "Healthcare",
    "PFE": "Healthcare",
    "MRK": "Healthcare",
    "ABBV": "Healthcare",
    "LLY": "Healthcare",
}


DEFAULT_INDUSTRIES = {
    "AAPL": "Consumer Electronics",
    "MSFT": "Software",
    "NVDA": "Semiconductors",
    "GOOGL": "Internet Content",
    "META": "Internet Content",
    "ORCL": "Software",
    "AMD": "Semiconductors",
    "JPM": "Banks",
    "BAC": "Banks",
    "WFC": "Banks",
    "GS": "Capital Markets",
    "MS": "Capital Markets",
    "XOM": "Oil & Gas Integrated",
    "CVX": "Oil & Gas Integrated",
    "COP": "Oil & Gas Exploration",
    "OXY": "Oil & Gas Exploration",
    "WMT": "Discount Stores",
    "COST": "Discount Stores",
    "TGT": "Discount Stores",
    "HD": "Home Improvement",
    "LOW": "Home Improvement",
    "JNJ": "Drug Manufacturers",
    "PFE": "Drug Manufacturers",
    "MRK": "Drug Manufacturers",
    "ABBV": "Drug Manufacturers",
    "LLY": "Drug Manufacturers",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate compact rolling correlation features."
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
        "--windows",
        nargs="+",
        type=int,
        default=[20, 60, 120],
    )
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--backend",
        choices=["numpy", "cupy"],
        default="numpy",
    )
    parser.add_argument(
        "--out",
        default="outputs/correlation/features.parquet",
        help="Output Parquet path.",
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

    return close


def main() -> None:
    args = parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tickers = list(dict.fromkeys(args.tickers))

    prices = download_adjusted_close(
        tickers=tickers,
        start=args.start,
        end=args.end,
    )

    return_matrix = prices_to_return_matrix(
        prices,
        tickers=tickers,
        min_non_nan_fraction=0.85,
    )

    metadata = build_asset_metadata(
        tickers=return_matrix.tickers,
        sectors=DEFAULT_SECTORS,
        industries=DEFAULT_INDUSTRIES,
    )

    tracker = CorrelationTracker(
        CorrelationTrackerConfig(
            windows=tuple(args.windows),
            step=args.step,
            top_k=args.top_k,
            backend=args.backend,
        )
    )

    features = tracker.compute_features(return_matrix, metadata)

    features.to_parquet(out_path, index=False)

    print(f"Saved {len(features):,} rows to {out_path}")
    print(features.tail(10))


if __name__ == "__main__":
    main()
