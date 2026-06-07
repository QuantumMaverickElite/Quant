# scripts/benchmark_same_universe_buy_hold.py

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark equal-weight buy-and-hold on the same price universe used by a Rust run."
    )

    parser.add_argument(
        "--prices-meta",
        required=True,
        help="Rust/export prices_meta.json file.",
    )
    parser.add_argument(
        "--orders-csv",
        required=True,
        help="Orders CSV used by the strategy. Used to infer strategy start date.",
    )
    parser.add_argument(
        "--out",
        default="outputs/reports/buy_hold_same_universe_equity.csv",
    )
    parser.add_argument(
        "--summary-out",
        default="outputs/reports/buy_hold_same_universe_summary.csv",
    )

    return parser.parse_args()


def max_drawdown(equity: np.ndarray) -> float:
    running_max = np.maximum.accumulate(equity)
    dd = equity / np.maximum(running_max, 1e-12) - 1.0
    return float(np.nanmin(dd))


def sharpe_like(equity: np.ndarray) -> float:
    returns = pd.Series(equity).pct_change().dropna()
    std = returns.std()

    if not np.isfinite(std) or std <= 0:
        return float("nan")

    return float(returns.mean() / std * np.sqrt(252))


def main() -> None:
    args = parse_args()

    meta_path = Path(args.prices_meta)
    orders_path = Path(args.orders_csv)

    meta = json.loads(meta_path.read_text())
    dtype = np.float32 if meta.get("dtype") == "float32" else np.float64

    prices = np.fromfile(meta_path.parent / meta["binary_file"], dtype=dtype)
    prices = prices.reshape(int(meta["rows"]), int(meta["cols"])).astype(float)

    tickers = meta.get("tickers") or meta.get("columns")
    raw_dates = meta.get("dates") or meta.get("index")

    if tickers is None or raw_dates is None:
        raise ValueError(f"Could not find tickers/dates in metadata keys: {list(meta.keys())}")

    dates = pd.to_datetime(raw_dates)

    orders = pd.read_csv(orders_path)

    if "entry_date" in orders.columns:
        start_date = pd.to_datetime(orders["entry_date"]).min()
    elif "signal_date" in orders.columns:
        start_date = pd.to_datetime(orders["signal_date"]).min()
    else:
        start_date = dates[0]

    start_idx = int(np.searchsorted(dates.values, np.datetime64(start_date), side="left"))

    start_prices = prices[start_idx]
    valid = np.isfinite(start_prices) & (start_prices > 0)

    prices_valid = prices[:, valid]
    start_prices_valid = start_prices[valid]

    relative = prices_valid / start_prices_valid
    relative[~np.isfinite(relative)] = np.nan

    equity = np.nanmean(relative, axis=1) * 10000.0

    dates_eval = dates[start_idx:]
    equity_eval = equity[start_idx:]

    dd_curve = equity_eval / np.maximum.accumulate(equity_eval) - 1.0

    ticker_returns = prices[-1, valid] / start_prices_valid - 1.0

    ticker_return_df = pd.DataFrame(
        {
            "ticker": np.array(tickers)[valid],
            "start_price": start_prices_valid,
            "end_price": prices[-1, valid],
            "buy_hold_return": ticker_returns,
        }
    ).sort_values("buy_hold_return", ascending=False)

    equity_df = pd.DataFrame(
        {
            "date": dates_eval,
            "equity": equity_eval,
            "drawdown": dd_curve,
        }
    )

    summary = pd.DataFrame(
        [
            {
                "benchmark": "same_universe_equal_weight_buy_hold",
                "start_date": dates_eval[0].date().isoformat(),
                "end_date": dates_eval[-1].date().isoformat(),
                "valid_tickers": int(valid.sum()),
                "initial_equity": 10000.0,
                "final_equity": float(equity_eval[-1]),
                "return_multiple": float(equity_eval[-1] / 10000.0),
                "total_return": float(equity_eval[-1] / 10000.0 - 1.0),
                "max_drawdown": max_drawdown(equity_eval),
                "sharpe_like": sharpe_like(equity_eval),
            }
        ]
    )

    out_path = Path(args.out)
    summary_path = Path(args.summary_out)
    ticker_path = summary_path.with_name(summary_path.stem.replace("_summary", "_ticker_returns") + ".csv")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    equity_df.to_csv(out_path, index=False)
    summary.to_csv(summary_path, index=False)
    ticker_return_df.to_csv(ticker_path, index=False)

    print(f"Saved buy-and-hold equity -> {out_path}")
    print(f"Saved buy-and-hold summary -> {summary_path}")
    print(f"Saved ticker returns -> {ticker_path}")
    print()
    print(summary.to_string(index=False))
    print()
    print("Top 20 buy-and-hold names:")
    print(ticker_return_df.head(20).to_string(index=False))
    print()
    print("Bottom 20 buy-and-hold names:")
    print(ticker_return_df.tail(20).to_string(index=False))


if __name__ == "__main__":
    main()
