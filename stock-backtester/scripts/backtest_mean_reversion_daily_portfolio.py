# scripts/backtest_mean_reversion_daily_portfolio.py

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf

from backtester.backtests.mean_reversion_daily_portfolio import (
    OpenPosition,
    mark_to_market,
    prepare_orders,
    run_daily_portfolio_backtest,
    summarize_daily_backtest,
)

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
        description="Daily overlapping-position backtest for context-adjusted mean reversion signals."
    )

    parser.add_argument(
        "--signals",
        default="outputs/signals/mean_reversion_signals_context_adjusted.parquet",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/backtests/mean_reversion_daily_portfolio_h5",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
    )
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default=None)

    parser.add_argument("--signal-horizon", type=int, default=5)
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--min-adjusted-confidence", type=float, default=0.10)
    parser.add_argument("--top-n-per-date", type=int, default=5)

    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    parser.add_argument(
        "--max-gross-exposure",
        type=float,
        default=1.0,
        help="Maximum total market value of open positions divided by equity.",
    )
    parser.add_argument(
        "--target-new-basket-exposure",
        type=float,
        default=0.20,
        help="Target fraction of equity allocated to each new signal-day basket.",
    )
    parser.add_argument(
        "--max-position-weight",
        type=float,
        default=0.10,
        help="Maximum fraction of equity allocated to a single new position.",
    )
    parser.add_argument(
        "--fee-bps",
        type=float,
        default=5.0,
        help="One-way fee/slippage estimate in basis points on entry and exit.",
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

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    signal_path = Path(args.signals)

    if not signal_path.exists():
        raise FileNotFoundError(f"Signal file not found: {signal_path}")

    signals = pd.read_parquet(signal_path)
    if signals.empty:
        raise RuntimeError("Signal file is empty.")

    tickers = list(dict.fromkeys(args.tickers))

    prices = download_adjusted_close(
        tickers=tickers,
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

    if orders.empty:
        raise RuntimeError("No orders generated with current filters.")

    trades, equity = run_daily_portfolio_backtest(
        orders,
        prices,
        initial_capital=args.initial_capital,
        max_gross_exposure=args.max_gross_exposure,
        target_new_basket_exposure=args.target_new_basket_exposure,
        max_position_weight=args.max_position_weight,
        fee_bps=args.fee_bps,
    )

    summary = summarize_daily_backtest(
        trades,
        equity,
        initial_capital=args.initial_capital,
    )

    orders_path = out_dir / "orders.parquet"
    trades_path = out_dir / "closed_trades.parquet"
    equity_path = out_dir / "daily_equity.parquet"
    summary_path = out_dir / "summary.csv"

    orders.to_parquet(orders_path, index=False)
    trades.to_parquet(trades_path, index=False)
    equity.to_parquet(equity_path, index=False)
    summary.to_csv(summary_path, index=False)

    print()
    print("=" * 80)
    print("Daily Overlapping-Position Mean Reversion Backtest")
    print("=" * 80)
    print(f"Signals: {args.signals}")
    print(f"Signal horizon: {args.signal_horizon}")
    print(f"Hold days: {args.hold_days}")
    print(f"Min adjusted confidence: {args.min_adjusted_confidence}")
    print(f"Top N per date: {args.top_n_per_date}")
    print(f"Initial capital: ${args.initial_capital:,.2f}")
    print(f"Max gross exposure: {args.max_gross_exposure:.2f}")
    print(f"Target new basket exposure: {args.target_new_basket_exposure:.2f}")
    print(f"Max position weight: {args.max_position_weight:.2f}")
    print(f"Fee bps one-way: {args.fee_bps:.2f}")

    print()
    print("Saved:")
    print(f"  {orders_path}")
    print(f"  {trades_path}")
    print(f"  {equity_path}")
    print(f"  {summary_path}")

    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(summary.to_string(index=False))

    print()
    print("=" * 80)
    print("Latest daily equity")
    print("=" * 80)
    print(equity.tail(20).to_string(index=False))

    print()
    print("=" * 80)
    print("Latest closed trades")
    print("=" * 80)
    if trades.empty:
        print("No closed trades.")
    else:
        print(trades.tail(30).to_string(index=False))


if __name__ == "__main__":
    main()
