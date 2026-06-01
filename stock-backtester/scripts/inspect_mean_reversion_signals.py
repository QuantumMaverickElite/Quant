# scripts/inspect_mean_reversion_signals.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect generated mean reversion signal output."
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals.parquet",
        help="Mean reversion signal parquet file.",
    )
    parser.add_argument(
        "--latest-only",
        action="store_true",
        help="Only show latest-date signal details.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Rows to show per section.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    path = Path(args.signals)

    if not path.exists():
        raise FileNotFoundError(f"Signal file not found: {path}")

    signals = pd.read_parquet(path)

    if signals.empty:
        print(f"Signal file is empty: {path}")
        return

    signals["date"] = pd.to_datetime(signals["date"])

    print()
    print("=" * 80)
    print("Mean Reversion Signal Inspection")
    print("=" * 80)
    print(f"Signal file: {path}")
    print(f"Rows: {len(signals):,}")
    print(
        f"Date range: {signals['date'].min().date()} → {signals['date'].max().date()}"
    )
    print(f"Tickers: {signals['ticker'].nunique():,}")
    print(f"Horizons: {sorted(signals['horizon'].unique().tolist())}")

    latest_date = signals["date"].max()
    latest = signals[signals["date"] == latest_date].copy()

    print()
    print("=" * 80)
    print(f"Latest signals: {latest_date.date()}")
    print("=" * 80)

    latest_cols = [
        "date",
        "ticker",
        "horizon",
        "direction",
        "confidence",
        "raw_score",
        "normalized_score",
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

    latest_cols = [col for col in latest_cols if col in latest.columns]

    latest_display = latest.sort_values(
        ["horizon", "confidence"],
        ascending=[True, False],
    )

    print(latest_display.loc[:, latest_cols].head(args.top).to_string(index=False))

    if args.latest_only:
        return

    print()
    print("=" * 80)
    print("Signal counts by horizon")
    print("=" * 80)
    print(
        signals.groupby("horizon")
        .size()
        .reset_index(name="signal_count")
        .sort_values("horizon")
        .to_string(index=False)
    )

    print()
    print("=" * 80)
    print("Most frequent signal tickers")
    print("=" * 80)
    print(
        signals.groupby("ticker")
        .agg(
            signal_count=("ticker", "count"),
            avg_confidence=("confidence", "mean"),
            max_confidence=("confidence", "max"),
            avg_peer_spread_z=("peer_spread_z", "mean"),
            min_peer_spread_z=("peer_spread_z", "min"),
        )
        .reset_index()
        .sort_values(["signal_count", "avg_confidence"], ascending=[False, False])
        .head(args.top)
        .to_string(index=False)
    )

    print()
    print("=" * 80)
    print("Highest confidence signals overall")
    print("=" * 80)
    print(
        signals.sort_values("confidence", ascending=False)
        .loc[:, latest_cols]
        .head(args.top)
        .to_string(index=False)
    )

    print()
    print("=" * 80)
    print("Signal count by date")
    print("=" * 80)
    daily = (
        signals.groupby("date")
        .agg(
            signal_count=("ticker", "count"),
            avg_confidence=("confidence", "mean"),
            max_confidence=("confidence", "max"),
            avg_peer_spread_z=("peer_spread_z", "mean"),
        )
        .reset_index()
    )

    print("Highest activity dates:")
    print(
        daily.sort_values("signal_count", ascending=False)
        .head(args.top)
        .to_string(index=False)
    )

    print()
    print("Latest activity dates:")
    print(
        daily.sort_values("date", ascending=False).head(args.top).to_string(index=False)
    )

    print()
    print("=" * 80)
    print("Signals by ticker and horizon")
    print("=" * 80)
    pivot = signals.pivot_table(
        index="ticker",
        columns="horizon",
        values="confidence",
        aggfunc="count",
        fill_value=0,
    ).reset_index()

    horizon_cols = [col for col in pivot.columns if col != "ticker"]
    pivot["total"] = pivot[horizon_cols].sum(axis=1)

    print(
        pivot.sort_values("total", ascending=False)
        .head(args.top)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
