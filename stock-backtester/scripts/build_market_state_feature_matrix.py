from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf
from tabulate import tabulate

from backtester.analytics.entropy import EntropyConfig
from backtester.decision.market_state_features import (
    build_feature_rows_for_ticker,
    build_rebalance_dates,
    compute_raw_momentum_scores,
    entropy_decision_from_row,
)

DEFAULT_VOLATILE_UNIVERSE = [
    "QBTS",
    "RGTI",
    "IONQ",
    "QUBT",
    "OKLO",
    "SMR",
    "RKLB",
    "ACHR",
    "JOBY",
    "SOUN",
    "AI",
    "MSTR",
    "COIN",
    "MARA",
    "RIOT",
    "CLSK",
    "HUT",
    "BITF",
    "HOOD",
    "UPST",
    "AFRM",
    "CVNA",
    "RIVN",
    "LCID",
    "TSLA",
    "PLTR",
    "SMCI",
    "ARM",
    "NVDA",
    "AMD",
    "MU",
    "APP",
]


def clean_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)

    out.columns = [str(col).lower() for col in out.columns]
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build fast MarketState feature matrix for Monte Carlo simulation."
    )

    parser.add_argument(
        "--tickers",
        "-t",
        nargs="+",
        default=DEFAULT_VOLATILE_UNIVERSE,
        help="Ticker universe.",
    )

    parser.add_argument(
        "--data-start",
        default="2018-01-01",
        help="Data start date. Default: 2018-01-01",
    )

    parser.add_argument(
        "--bt-start",
        default="2025-01-01",
        help="Backtest start date. Default: 2025-01-01",
    )

    parser.add_argument(
        "--bt-end",
        default="2026-01-01",
        help="Backtest end date. Default: 2026-01-01",
    )

    parser.add_argument(
        "--rebalance",
        choices=["D", "W", "B", "3W", "M", "6W", "Q"],
        default="M",
        help=(
            "Rebalance frequency: D=daily, W=weekly, B=bi-weekly, 3W=every 3 weeks, M=monthly, 6W=every 6 weeks, Q=quarterly. "
            "Default: M"
        ),
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
        help="Entropy/volatility percentile window. Default: 252",
    )

    parser.add_argument(
        "--bins",
        type=int,
        default=10,
        help="Number of entropy bins. Default: 10",
    )

    parser.add_argument(
        "--output-dir",
        default="outputs/feature_matrix/market_state_v1",
        help="Output directory.",
    )

    return parser.parse_args()


def download_prices(
    tickers: list[str],
    data_start: str,
    bt_end: str,
) -> dict[str, pd.DataFrame]:
    data = {}

    for ticker in tickers:
        print(f"Downloading {ticker}...")

        df = yf.download(
            ticker,
            start=data_start,
            end=bt_end,
            auto_adjust=True,
            progress=False,
        )

        if df.empty:
            print(f"  WARNING: no data for {ticker}, skipping.")
            continue

        df = clean_yfinance_columns(df)

        if "close" not in df.columns:
            print(f"  WARNING: {ticker} missing close column, skipping.")
            continue

        data[ticker] = df

    return data


def main() -> None:
    args = parse_args()

    tickers = sorted(set(t.upper() for t in args.tickers))

    print("\nBuilding MarketState Feature Matrix")
    print(f"Tickers: {len(tickers)}")
    print(f"Data start: {args.data_start}")
    print(f"Backtest window: {args.bt_start} to {args.bt_end}")
    print(f"Rebalance: {args.rebalance}")

    data = download_prices(
        tickers=tickers,
        data_start=args.data_start,
        bt_end=args.bt_end,
    )

    if not data:
        raise ValueError("No usable ticker data downloaded.")

    close_matrix = (
        pd.concat(
            {ticker: df["close"] for ticker, df in data.items()},
            axis=1,
        )
        .sort_index()
        .ffill()
    )

    common_index = pd.DatetimeIndex(
        sorted(set().union(*[df.index for df in data.values()]))
    )

    rebalance_dates = build_rebalance_dates(
        trading_index=common_index,
        bt_start=args.bt_start,
        bt_end=args.bt_end,
        freq=args.rebalance,
    )

    if not rebalance_dates:
        raise ValueError("No rebalance dates found.")

    print("\nRebalance dates:")
    print(", ".join(str(d.date()) for d in rebalance_dates))

    entropy_config = EntropyConfig(
        price_col="close",
        entropy_window=args.entropy_window,
        zscore_window=args.zscore_window,
        n_bins=args.bins,
    )

    feature_rows = []

    for ticker, prices in data.items():
        print(f"Computing features for {ticker}...")

        rows = build_feature_rows_for_ticker(
            ticker=ticker,
            prices=prices,
            rebalance_dates=rebalance_dates,
            entropy_config=entropy_config,
            zscore_window=args.zscore_window,
        )

        feature_rows.extend(rows)

    features = pd.DataFrame(feature_rows)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    feature_path = output_dir / "market_state_features.csv"
    close_path = output_dir / "close_prices.csv"
    metadata_path = output_dir / "metadata.csv"

    features.to_csv(feature_path, index=False)
    close_matrix.to_csv(close_path)

    metadata = pd.DataFrame(
        [
            {
                "data_start": args.data_start,
                "bt_start": args.bt_start,
                "bt_end": args.bt_end,
                "rebalance": args.rebalance,
                "entropy_window": args.entropy_window,
                "zscore_window": args.zscore_window,
                "bins": args.bins,
                "tickers": " ".join(tickers),
            }
        ]
    )
    metadata.to_csv(metadata_path, index=False)

    print("\nFeature Matrix Summary:")
    summary = pd.DataFrame(
        [
            {
                "tickers_requested": len(tickers),
                "tickers_downloaded": len(data),
                "feature_rows": len(features),
                "rebalance_dates": len(rebalance_dates),
            }
        ]
    )
    print(tabulate(summary, headers="keys", tablefmt="github", showindex=False))

    if not features.empty:
        preview_cols = [
            "date",
            "ticker",
            "vol_regime",
            "return_entropy_regime",
            "direction_entropy_regime",
            "combined_multiplier",
            "capital_posture",
            "raw_score",
            "adjusted_score",
        ]
        preview_cols = [c for c in preview_cols if c in features.columns]

        print("\nPreview:")
        print(
            tabulate(
                features[preview_cols].tail(20),
                headers="keys",
                tablefmt="github",
                showindex=False,
            )
        )

    print("\nSaved outputs:")
    print(f"  Features: {feature_path}")
    print(f"  Prices:   {close_path}")
    print(f"  Metadata: {metadata_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
