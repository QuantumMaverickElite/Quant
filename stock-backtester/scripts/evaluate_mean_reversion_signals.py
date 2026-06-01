# scripts/evaluate_mean_reversion_signals.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

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
        description="Evaluate forward returns after mean reversion signals."
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals.parquet",
        help="Mean reversion signal parquet file.",
    )
    parser.add_argument(
        "--out",
        default="outputs/signals/mean_reversion_evaluation.parquet",
        help="Output evaluation parquet file.",
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
        "--forward-horizons",
        nargs="+",
        type=int,
        default=[1, 5, 10, 20],
        help="Forward return horizons to evaluate.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="Rows to print per section.",
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


def add_forward_returns(
    signals: pd.DataFrame,
    prices: pd.DataFrame,
    forward_horizons: list[int],
) -> pd.DataFrame:
    signals = signals.copy()
    signals["date"] = pd.to_datetime(signals["date"])

    prices = prices.copy()
    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()

    out = signals.copy()

    for horizon in forward_horizons:
        future_returns = prices.shift(-horizon) / prices - 1.0

        long_future = (
            future_returns.reset_index()
            .melt(
                id_vars=future_returns.index.name or "index",
                var_name="ticker",
                value_name=f"future_return_{horizon}d",
            )
            .rename(columns={future_returns.index.name or "index": "date"})
        )

        out = out.merge(
            long_future,
            on=["date", "ticker"],
            how="left",
        )

    return out


def summarize_by_horizon(
    evaluated: pd.DataFrame, forward_horizons: list[int]
) -> pd.DataFrame:
    rows = []

    for signal_horizon, group in evaluated.groupby("horizon"):
        for fwd in forward_horizons:
            col = f"future_return_{fwd}d"

            if col not in group.columns:
                continue

            vals = group[col].dropna()

            if vals.empty:
                continue

            rows.append(
                {
                    "signal_horizon": signal_horizon,
                    "forward_horizon": fwd,
                    "count": int(vals.count()),
                    "mean_return": float(vals.mean()),
                    "median_return": float(vals.median()),
                    "win_rate": float((vals > 0).mean()),
                    "avg_confidence": float(group.loc[vals.index, "confidence"].mean()),
                }
            )

    return pd.DataFrame(rows)


def summarize_by_confidence_bucket(
    evaluated: pd.DataFrame,
    forward_horizons: list[int],
) -> pd.DataFrame:
    frame = evaluated.copy()

    frame["confidence_bucket"] = pd.qcut(
        frame["confidence"].rank(method="first"),
        q=4,
        labels=["Q1_low", "Q2", "Q3", "Q4_high"],
    )

    rows = []

    for (signal_horizon, bucket), group in frame.groupby(
        ["horizon", "confidence_bucket"], observed=True
    ):
        for fwd in forward_horizons:
            col = f"future_return_{fwd}d"

            if col not in group.columns:
                continue

            vals = group[col].dropna()

            if vals.empty:
                continue

            rows.append(
                {
                    "signal_horizon": signal_horizon,
                    "confidence_bucket": str(bucket),
                    "forward_horizon": fwd,
                    "count": int(vals.count()),
                    "mean_return": float(vals.mean()),
                    "median_return": float(vals.median()),
                    "win_rate": float((vals > 0).mean()),
                    "avg_confidence": float(group.loc[vals.index, "confidence"].mean()),
                }
            )

    return pd.DataFrame(rows)


def summarize_by_ticker(
    evaluated: pd.DataFrame,
    forward_horizon: int,
) -> pd.DataFrame:
    col = f"future_return_{forward_horizon}d"

    if col not in evaluated.columns:
        raise ValueError(f"Missing column: {col}")

    return (
        evaluated.dropna(subset=[col])
        .groupby("ticker")
        .agg(
            signal_count=("ticker", "count"),
            mean_forward_return=(col, "mean"),
            median_forward_return=(col, "median"),
            win_rate=(col, lambda s: (s > 0).mean()),
            avg_confidence=("confidence", "mean"),
            max_confidence=("confidence", "max"),
        )
        .reset_index()
        .sort_values(["mean_forward_return", "signal_count"], ascending=[False, False])
    )


def main() -> None:
    args = parse_args()

    signal_path = Path(args.signals)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not signal_path.exists():
        raise FileNotFoundError(f"Signal file not found: {signal_path}")

    tickers = list(dict.fromkeys(args.tickers))

    signals = pd.read_parquet(signal_path)

    if signals.empty:
        raise RuntimeError("Signal file is empty.")

    prices = download_adjusted_close(
        tickers=tickers,
        start=args.start,
        end=args.end,
    )

    evaluated = add_forward_returns(
        signals=signals,
        prices=prices,
        forward_horizons=args.forward_horizons,
    )

    evaluated.to_parquet(out_path, index=False)

    print()
    print("=" * 80)
    print("Mean Reversion Forward-Return Evaluation")
    print("=" * 80)
    print(f"Saved {len(evaluated):,} evaluated signal rows to {out_path}")
    print(
        f"Signal date range: {evaluated['date'].min().date()} → {evaluated['date'].max().date()}"
    )
    print(f"Forward horizons: {args.forward_horizons}")

    print()
    print("=" * 80)
    print("Summary by signal horizon")
    print("=" * 80)
    summary = summarize_by_horizon(evaluated, args.forward_horizons)
    print(summary.to_string(index=False))

    print()
    print("=" * 80)
    print("Summary by confidence bucket")
    print("=" * 80)
    buckets = summarize_by_confidence_bucket(evaluated, args.forward_horizons)
    print(buckets.to_string(index=False))

    main_forward = 5 if 5 in args.forward_horizons else args.forward_horizons[0]

    print()
    print("=" * 80)
    print(f"Best tickers by future {main_forward}d return")
    print("=" * 80)
    ticker_summary = summarize_by_ticker(evaluated, main_forward)
    print(ticker_summary.head(args.top).to_string(index=False))

    print()
    print("=" * 80)
    print(f"Worst tickers by future {main_forward}d return")
    print("=" * 80)
    print(ticker_summary.tail(args.top).to_string(index=False))

    print()
    print("=" * 80)
    print("Highest-confidence evaluated signals")
    print("=" * 80)

    display_cols = [
        "date",
        "ticker",
        "horizon",
        "direction",
        "confidence",
        "peer_spread_z",
        "peer_spread",
        "stock_return",
        "peer_basket_return",
    ] + [f"future_return_{h}d" for h in args.forward_horizons]

    display_cols = [col for col in display_cols if col in evaluated.columns]

    print(
        evaluated.sort_values("confidence", ascending=False)
        .loc[:, display_cols]
        .head(args.top)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
