# scripts/export_orders_from_signals_with_cached_prices.py

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export Rust orders from signal parquet using an existing cached prices_meta.json."
    )

    p.add_argument("--signals", required=True)
    p.add_argument("--prices-meta", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--signal-horizon", type=int, default=100)
    p.add_argument("--hold-days", type=int, default=100)
    p.add_argument("--min-adjusted-confidence", type=float, default=0.10)
    p.add_argument("--top-n-per-date", type=int, default=5)

    return p.parse_args()


def main() -> None:
    args = parse_args()

    signals = pd.read_parquet(args.signals).copy()

    required = {"date", "ticker", "horizon", "adjusted_confidence", "peer_spread_z"}
    missing = required - set(signals.columns)
    if missing:
        raise ValueError(f"Signals missing required columns: {sorted(missing)}")

    meta_path = Path(args.prices_meta)
    meta = json.loads(meta_path.read_text())

    tickers = meta.get("tickers") or meta.get("columns")
    dates = pd.to_datetime(meta.get("dates") or meta.get("index"))

    if tickers is None or dates is None:
        raise ValueError(f"Could not find tickers/dates in prices metadata. Keys: {list(meta.keys())}")

    price_tickers = set(str(t).upper().strip() for t in tickers)
    price_dates = pd.DatetimeIndex(dates).sort_values()

    signals["date"] = pd.to_datetime(signals["date"])
    signals["ticker"] = signals["ticker"].astype(str).str.upper().str.strip()
    signals["adjusted_confidence"] = signals["adjusted_confidence"].astype(float)

    signals = signals[signals["date"].ge(pd.Timestamp(args.start))].copy()
    signals = signals[signals["horizon"].astype(int).eq(args.signal_horizon)].copy()
    signals = signals[signals["ticker"].isin(price_tickers)].copy()
    signals = signals[signals["adjusted_confidence"].ge(args.min_adjusted_confidence)].copy()

    if signals.empty:
        raise SystemExit("No signals survived filtering.")

    signals = signals.sort_values(["date", "adjusted_confidence"], ascending=[True, False])
    signals = signals.groupby("date", as_index=False, group_keys=False).head(args.top_n_per_date)

    rows = []

    for _, r in signals.iterrows():
        signal_date = pd.Timestamp(r["date"])

        entry_pos = price_dates.searchsorted(signal_date, side="right")
        exit_pos = entry_pos + args.hold_days

        if entry_pos >= len(price_dates) or exit_pos >= len(price_dates):
            continue

        rows.append(
            {
                "signal_date": signal_date.date().isoformat(),
                "entry_date": price_dates[entry_pos].date().isoformat(),
                "exit_date": price_dates[exit_pos].date().isoformat(),
                "ticker": r["ticker"],
                "adjusted_confidence": float(r["adjusted_confidence"]),
                "peer_spread_z": float(r["peer_spread_z"]),
            }
        )

    orders = pd.DataFrame(rows)

    if orders.empty:
        raise SystemExit("No valid orders after date alignment.")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    orders_path = out_dir / "orders.csv"
    orders.to_csv(orders_path, index=False)

    print(f"Saved orders: {orders_path} ({len(orders):,} rows)")
    print()
    print("Order summary:")
    print("  order_rows:", len(orders))
    print("  order_tickers:", orders["ticker"].nunique())
    print("  first_signal_date:", orders["signal_date"].min())
    print("  last_signal_date:", orders["signal_date"].max())
    print()
    print(orders.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
