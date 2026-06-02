# scripts/filter_peer_spread_signals_with_cooldown.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Filter peer-spread candidates by market context and ticker cooldown."
    )
    parser.add_argument("--signals", required=True, help="Input candidate parquet.")
    parser.add_argument("--out", required=True, help="Output selected signal parquet.")
    parser.add_argument("--top-n-per-date", type=int, default=5)
    parser.add_argument("--cooldown-days", type=int, default=60)
    parser.add_argument("--exclude-context-bucket", action="append", default=[])
    parser.add_argument("--exclude-volatility-state", action="append", default=[])
    parser.add_argument("--min-adjusted-confidence", type=float, default=0.0)
    parser.add_argument("--min-avg-peer-corr", type=float, default=0.0)
    parser.add_argument("--min-spread-obs", type=float, default=0.0)
    parser.add_argument("--require-long", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    src = Path(args.signals)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(src).copy()
    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper()

    before = len(df)

    if args.exclude_context_bucket:
        excluded = {x.lower() for x in args.exclude_context_bucket}
        df = df[~df["context_weight_bucket"].astype(str).str.lower().isin(excluded)].copy()

    if args.exclude_volatility_state:
        excluded = {x.lower() for x in args.exclude_volatility_state}
        df = df[~df["volatility_state"].astype(str).str.lower().isin(excluded)].copy()

    if args.require_long and "direction" in df.columns:
        df = df[df["direction"].astype(str).str.lower().eq("long")].copy()

    df = df[df["adjusted_confidence"] >= args.min_adjusted_confidence].copy()

    if "avg_peer_corr" in df.columns:
        df = df[df["avg_peer_corr"] >= args.min_avg_peer_corr].copy()

    if "spread_obs" in df.columns:
        df = df[df["spread_obs"] >= args.min_spread_obs].copy()

    df = df.sort_values(["date", "adjusted_confidence"], ascending=[True, False]).reset_index(drop=True)

    unique_dates = sorted(df["date"].unique())
    date_to_idx = {date: i for i, date in enumerate(unique_dates)}

    selected_rows = []
    last_selected_idx_by_ticker: dict[str, int] = {}

    for date, group in df.groupby("date", sort=True):
        date_idx = date_to_idx[date]
        picked = 0

        for _, row in group.iterrows():
            ticker = row["ticker"]
            last_idx = last_selected_idx_by_ticker.get(ticker)

            if last_idx is not None and date_idx - last_idx <= args.cooldown_days:
                continue

            selected_rows.append(row)
            last_selected_idx_by_ticker[ticker] = date_idx
            picked += 1

            if picked >= args.top_n_per_date:
                break

    selected = pd.DataFrame(selected_rows)

    if not selected.empty:
        selected = selected.sort_values(["date", "adjusted_confidence"], ascending=[True, False]).reset_index(drop=True)

    selected.to_parquet(out, index=False)

    print()
    print("=" * 80)
    print("Peer-spread cooldown filter complete")
    print("=" * 80)
    print(f"input: {src}")
    print(f"output: {out}")
    print(f"input rows: {before:,}")
    print(f"rows after context/basic filters: {len(df):,}")
    print(f"selected rows: {len(selected):,}")
    print(f"dates: {selected['date'].nunique() if not selected.empty else 0:,}")
    print(f"tickers: {selected['ticker'].nunique() if not selected.empty else 0:,}")
    print(f"top_n_per_date: {args.top_n_per_date}")
    print(f"cooldown_days: {args.cooldown_days}")
    print(f"exclude_context_bucket: {args.exclude_context_bucket}")
    print(f"exclude_volatility_state: {args.exclude_volatility_state}")

    if not selected.empty:
        print()
        print("Most common selected tickers:")
        print(selected["ticker"].value_counts().head(30).to_string())

        if "context_weight_bucket" in selected.columns:
            print()
            print("Context bucket counts:")
            print(selected["context_weight_bucket"].value_counts(dropna=False).to_string())

        if "volatility_state" in selected.columns:
            print()
            print("Volatility state counts:")
            print(selected["volatility_state"].value_counts(dropna=False).to_string())

        print()
        print("CHRD rows:", int((selected["ticker"] == "CHRD").sum()))
        print()
        print("Sample:")
        cols = [
            c for c in [
                "date", "ticker", "adjusted_confidence", "peer_spread_z",
                "volatility_state", "entropy_state", "context_weight_bucket",
            ]
            if c in selected.columns
        ]
        print(selected[cols].head(30).to_string(index=False))


if __name__ == "__main__":
    main()
