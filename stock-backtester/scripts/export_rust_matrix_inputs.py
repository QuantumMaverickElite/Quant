# scripts/export_rust_matrix_inputs.py

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Rust-ready binary price matrix and orders."
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals_context_adjusted.parquet",
    )
    parser.add_argument("--out-dir", default="/tmp/quant_rust_matrix/h100")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--signal-horizon", type=int, default=100)
    parser.add_argument("--hold-days", type=int, default=100)
    parser.add_argument("--min-adjusted-confidence", type=float, default=0.10)
    parser.add_argument("--top-n-per-date", type=int, default=5)
    parser.add_argument(
        "--universe-file", default="data/universes/liquid_large_mid.txt"
    )
    parser.add_argument(
        "--dtype",
        choices=["float32", "float64"],
        default="float32",
        help="Matrix dtype. Use float32 for large universes.",
    )

    return parser.parse_args()


def load_universe(path: str) -> list[str]:
    p = Path(path)

    if not p.exists():
        raise FileNotFoundError(p)

    tickers = [
        line.strip().upper().replace(".", "-")
        for line in p.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    out = []
    seen = set()

    for ticker in tickers:
        if ticker and ticker not in seen:
            out.append(ticker)
            seen.add(ticker)

    return out


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
        progress=True,
        group_by="column",
        threads=True,
    )

    if data.empty:
        raise RuntimeError("No price data downloaded.")

    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"]
    else:
        close = data[["Close"]]
        close.columns = tickers[:1]

    close.index = pd.to_datetime(close.index)
    close = close.sort_index()
    close = close.dropna(axis=1, how="all")

    return close


def prepare_orders(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    signal_horizon: int,
    hold_days: int,
    min_adjusted_confidence: float,
    top_n_per_date: int,
) -> pd.DataFrame:
    frame = signals.copy()
    frame["date"] = pd.to_datetime(frame["date"])

    frame = frame[
        (frame["horizon"] == signal_horizon)
        & (frame["adjusted_confidence"] >= min_adjusted_confidence)
    ].copy()

    frame = frame.sort_values(
        ["date", "adjusted_confidence"],
        ascending=[True, False],
    )

    frame = frame.groupby("date", group_keys=False).head(top_n_per_date).copy()

    trading_dates = pd.DatetimeIndex(prices.index)
    date_to_idx = {pd.Timestamp(date): i for i, date in enumerate(trading_dates)}

    entry_dates = []
    exit_dates = []

    for signal_date in frame["date"]:
        idx = date_to_idx.get(pd.Timestamp(signal_date))

        if idx is None:
            entry_dates.append(pd.NaT)
            exit_dates.append(pd.NaT)
            continue

        entry_idx = idx + 1
        exit_idx = idx + 1 + hold_days

        if entry_idx >= len(trading_dates) or exit_idx >= len(trading_dates):
            entry_dates.append(pd.NaT)
            exit_dates.append(pd.NaT)
            continue

        entry_dates.append(pd.Timestamp(trading_dates[entry_idx]))
        exit_dates.append(pd.Timestamp(trading_dates[exit_idx]))

    frame["signal_date"] = frame["date"]
    frame["entry_date"] = entry_dates
    frame["exit_date"] = exit_dates

    frame = frame.dropna(subset=["entry_date", "exit_date"]).copy()

    keep_cols = [
        "signal_date",
        "entry_date",
        "exit_date",
        "ticker",
        "adjusted_confidence",
        "peer_spread_z",
    ]

    frame = frame.loc[:, keep_cols].copy()

    for col in ["signal_date", "entry_date", "exit_date"]:
        frame[col] = pd.to_datetime(frame[col]).dt.strftime("%Y-%m-%d")

    return frame


def main() -> None:
    args = parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    signals = pd.read_parquet(args.signals)

    universe = load_universe(args.universe_file)

    for ticker in sorted(signals["ticker"].unique()):
        ticker = str(ticker).upper().replace(".", "-")
        if ticker not in universe:
            universe.append(ticker)

    prices = download_adjusted_close(
        universe,
        start=args.start,
        end=args.end,
    )

    orders = prepare_orders(
        signals,
        prices,
        signal_horizon=args.signal_horizon,
        hold_days=args.hold_days,
        min_adjusted_confidence=args.min_adjusted_confidence,
        top_n_per_date=args.top_n_per_date,
    )

    dtype = np.float32 if args.dtype == "float32" else np.float64

    matrix = prices.to_numpy(dtype=dtype, copy=True)

    prices_bin_path = out_dir / "prices.bin"
    meta_path = out_dir / "prices_meta.json"
    orders_path = out_dir / "orders.csv"

    matrix.tofile(prices_bin_path)

    meta = {
        "format": "row_major_price_matrix",
        "dtype": args.dtype,
        "rows": int(matrix.shape[0]),
        "cols": int(matrix.shape[1]),
        "dates": [pd.Timestamp(d).strftime("%Y-%m-%d") for d in prices.index],
        "tickers": [str(c) for c in prices.columns],
        "binary_file": prices_bin_path.name,
    }

    meta_path.write_text(json.dumps(meta))

    orders.to_csv(orders_path, index=False)

    print(f"Saved orders: {orders_path} ({len(orders):,} rows)")
    print(f"Saved prices binary: {prices_bin_path}")
    print(f"Saved prices metadata: {meta_path}")
    print(f"Matrix shape: {matrix.shape[0]:,} rows × {matrix.shape[1]:,} tickers")
    print(f"Matrix dtype: {args.dtype}")
    print(f"Approx binary size: {prices_bin_path.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
