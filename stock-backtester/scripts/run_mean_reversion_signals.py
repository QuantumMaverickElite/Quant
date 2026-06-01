# scripts/run_mean_reversion_signals.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from backtester.signals import build_mean_reversion_signals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate mean reversion signals from peer spread features."
    )

    parser.add_argument(
        "--spreads",
        default="outputs/correlation/peer_spreads.parquet",
        help="Peer spread feature parquet file.",
    )
    parser.add_argument(
        "--out",
        default="outputs/signals/mean_reversion_signals.parquet",
        help="Output signal parquet file.",
    )
    parser.add_argument(
        "--min-abs-z",
        type=float,
        default=1.5,
        help="Minimum absolute peer spread z-score required.",
    )
    parser.add_argument(
        "--min-peer-corr",
        type=float,
        default=0.30,
        help="Minimum top-k average peer correlation required.",
    )
    parser.add_argument(
        "--allow-short",
        action="store_true",
        help="Allow both long and short signals. Default is long-only.",
    )
    parser.add_argument(
        "--latest-only",
        action="store_true",
        help="Print only the latest-date signals.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="Rows to print.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    spread_path = Path(args.spreads)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not spread_path.exists():
        raise FileNotFoundError(f"Peer spread file not found: {spread_path}")

    spreads = pd.read_parquet(spread_path)

    signals = build_mean_reversion_signals(
        spreads,
        min_abs_z=args.min_abs_z,
        min_peer_corr=args.min_peer_corr,
        long_only=not args.allow_short,
    )

    signals.to_parquet(out_path, index=False)

    print(f"Saved {len(signals):,} rows to {out_path}")

    if signals.empty:
        print("No signals generated with current thresholds.")
        return

    display = signals.copy()

    if args.latest_only:
        latest = display["date"].max()
        display = display[display["date"] == latest].copy()
        print(f"Latest signal date: {latest.date()}")

    display = display.sort_values(
        ["date", "horizon", "confidence"],
        ascending=[False, True, False],
    )

    cols = [
        "date",
        "ticker",
        "horizon",
        "direction",
        "confidence",
        "raw_score",
        "peer_spread_z",
        "peer_spread",
        "stock_return",
        "peer_basket_return",
        "top_k_avg_corr",
        "peer_1",
        "peer_2",
        "peer_3",
        "peer_4",
        "peer_5",
    ]

    existing_cols = [col for col in cols if col in display.columns]

    print(display.loc[:, existing_cols].head(args.top).to_string(index=False))


if __name__ == "__main__":
    main()
