# scripts/run_market_context_features.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

from backtester.context import build_market_context_features

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
        description="Generate market context features from price data."
    )

    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="Ticker universe.",
    )
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--vol-window", type=int, default=20)
    parser.add_argument("--z-window", type=int, default=120)
    parser.add_argument("--entropy-window", type=int, default=20)
    parser.add_argument(
        "--out",
        default="outputs/context/market_context.parquet",
        help="Output market context parquet file.",
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

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tickers = list(dict.fromkeys(args.tickers))

    prices = download_adjusted_close(
        tickers=tickers,
        start=args.start,
        end=args.end,
    )

    context = build_market_context_features(
        prices,
        vol_window=args.vol_window,
        z_window=args.z_window,
        entropy_window=args.entropy_window,
    )

    context.to_parquet(out_path, index=False)

    print(f"Saved {len(context):,} rows to {out_path}")
    print(context.tail(30).to_string(index=False))


if __name__ == "__main__":
    main()
