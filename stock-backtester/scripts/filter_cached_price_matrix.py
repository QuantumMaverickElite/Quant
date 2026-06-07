# scripts/filter_cached_price_matrix.py

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Filter cached price matrix to remove bad adjusted-price histories."
    )

    p.add_argument(
        "--prices-meta",
        default="outputs/cache/matrices/h100_market_common_stock_only_v3/prices_meta.json",
    )
    p.add_argument(
        "--out-dir",
        default="outputs/cache/matrices/h100_market_common_stock_only_v3_clean",
    )
    p.add_argument("--min-valid-coverage", type=float, default=0.90)
    p.add_argument("--min-start-price", type=float, default=0.25)
    p.add_argument("--max-start-price", type=float, default=100000.0)
    p.add_argument("--min-end-price", type=float, default=0.25)
    p.add_argument("--max-end-price", type=float, default=100000.0)
    p.add_argument("--max-full-return", type=float, default=100.0)
    p.add_argument("--min-full-return", type=float, default=-0.98)
    p.add_argument("--max-one-day-return", type=float, default=5.0)
    p.add_argument("--min-one-day-return", type=float, default=-0.90)

    return p.parse_args()


def main() -> None:
    args = parse_args()

    meta_path = Path(args.prices_meta)
    meta = json.loads(meta_path.read_text())

    dtype = np.float32 if meta.get("dtype", "float32") == "float32" else np.float64

    prices = np.fromfile(meta_path.parent / meta["binary_file"], dtype=dtype)
    prices = prices.reshape(int(meta["rows"]), int(meta["cols"])).astype(np.float32)

    tickers = meta.get("tickers") or meta.get("columns")
    dates = pd.to_datetime(meta.get("dates") or meta.get("index"))

    if tickers is None or dates is None:
        raise ValueError(f"Missing tickers/dates in metadata keys: {list(meta.keys())}")

    tickers = np.array([str(t).upper().strip() for t in tickers])
    dates = pd.DatetimeIndex(dates)

    valid = np.isfinite(prices) & (prices > 0)
    coverage = valid.mean(axis=0)

    # Use the first and final matrix dates, not each ticker's first/last valid point.
    # This keeps the buy-and-hold benchmark honest and avoids final-date NaN names.
    first_price = prices[0].astype(np.float64)
    last_price = prices[-1].astype(np.float64)

    first_price[~np.isfinite(first_price) | (first_price <= 0)] = np.nan
    last_price[~np.isfinite(last_price) | (last_price <= 0)] = np.nan

    full_return = last_price / first_price - 1.0

    daily_returns = prices[1:] / prices[:-1] - 1.0
    daily_returns[~np.isfinite(daily_returns)] = np.nan

    max_daily_return = np.nanmax(daily_returns, axis=0)
    min_daily_return = np.nanmin(daily_returns, axis=0)

    checks = pd.DataFrame(
        {
            "ticker": tickers,
            "valid_coverage": coverage,
            "first_price": first_price,
            "last_price": last_price,
            "full_return": full_return,
            "max_daily_return": max_daily_return,
            "min_daily_return": min_daily_return,
        }
    )

    checks["pass_valid_coverage"] = checks["valid_coverage"].ge(args.min_valid_coverage)
    checks["pass_first_price"] = checks["first_price"].between(args.min_start_price, args.max_start_price)
    checks["pass_last_price"] = checks["last_price"].between(args.min_end_price, args.max_end_price)
    checks["pass_full_return"] = checks["full_return"].between(args.min_full_return, args.max_full_return)
    checks["pass_daily_jump"] = (
        checks["max_daily_return"].le(args.max_one_day_return)
        & checks["min_daily_return"].ge(args.min_one_day_return)
    )

    pass_cols = [c for c in checks.columns if c.startswith("pass_")]
    keep = checks[pass_cols].all(axis=1).to_numpy()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    clean_prices = prices[:, keep].astype(dtype)
    clean_tickers = tickers[keep].tolist()

    clean_prices.tofile(out_dir / "prices.bin")

    new_meta = dict(meta)
    new_meta["rows"] = int(clean_prices.shape[0])
    new_meta["cols"] = int(clean_prices.shape[1])
    new_meta["binary_file"] = "prices.bin"
    new_meta["tickers"] = clean_tickers
    new_meta["columns"] = clean_tickers
    new_meta["dates"] = [d.strftime("%Y-%m-%d") for d in dates]
    new_meta["index"] = [d.strftime("%Y-%m-%d") for d in dates]
    new_meta["dtype"] = "float32" if dtype == np.float32 else "float64"
    new_meta["source_prices_meta"] = str(meta_path)

    (out_dir / "prices_meta.json").write_text(json.dumps(new_meta, indent=2))

    checks["kept"] = keep
    checks.to_csv(out_dir / "price_filter_report.csv", index=False)

    fail_counts = (~checks[pass_cols]).sum().sort_values(ascending=False)
    fail_counts.to_csv(out_dir / "price_filter_fail_counts.csv", header=["failed_count"])

    print("Price matrix filter complete")
    print(f"source: {meta_path}")
    print(f"out:    {out_dir / 'prices_meta.json'}")
    print()
    print(f"before tickers: {len(tickers):,}")
    print(f"after tickers:  {len(clean_tickers):,}")
    print(f"removed:        {len(tickers) - len(clean_tickers):,} ({(len(tickers)-len(clean_tickers))/len(tickers):.2%})")
    print()
    print("failed checks:")
    print(fail_counts.to_string())
    print()
    print("worst removed by full_return:")
    print(
        checks[~checks["kept"]]
        .sort_values("full_return")
        .head(20)
        .to_string(index=False)
    )
    print()
    print("largest removed by full_return:")
    print(
        checks[~checks["kept"]]
        .sort_values("full_return", ascending=False)
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
