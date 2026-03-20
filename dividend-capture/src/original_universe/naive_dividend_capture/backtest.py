#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from typing import List, Optional

import pandas as pd
import yfinance as yf


@dataclass
class TradeResult:
    ticker: str
    ex_date: str
    buy_date: str
    sell_date: str
    dividend: float
    buy_price: float
    sell_price: float
    shares: float
    gross_pnl: float
    gross_return_pct: float
    drop_ratio: float


def make_index_naive(idx: pd.Index) -> pd.Index:
    idx = pd.to_datetime(idx)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return idx


def get_trading_day_index(price_df: pd.DataFrame, target_date: pd.Timestamp) -> Optional[int]:
    idx = price_df.index

    if target_date in idx:
        return idx.get_loc(target_date)

    later = idx[idx > target_date]
    if len(later) == 0:
        return None
    return idx.get_loc(later[0])


def backtest_ticker(
    ticker: str,
    start: str,
    end: str,
    hold_days: int,
    capital_per_trade: float,
) -> List[TradeResult]:
    tk = yf.Ticker(ticker)

    price_df = tk.history(start=start, end=end, auto_adjust=False)
    if price_df.empty:
        return []

    price_df = price_df[["Open", "High", "Low", "Close", "Volume"]].copy()
    price_df.index = make_index_naive(price_df.index)
    price_df = price_df.sort_index()

    dividends = tk.dividends
    if dividends is None or len(dividends) == 0:
        return []

    dividends.index = make_index_naive(dividends.index)
    dividends = dividends.sort_index()
    dividends = dividends[
        (dividends.index >= pd.Timestamp(start)) &
        (dividends.index < pd.Timestamp(end))
    ]

    trades: List[TradeResult] = []

    for ex_date, dividend in dividends.items():
        ex_date = pd.Timestamp(ex_date)

        ex_idx = get_trading_day_index(price_df, ex_date)
        if ex_idx is None:
            continue

        buy_idx = ex_idx - 1
        sell_idx = ex_idx + hold_days

        if buy_idx < 0 or sell_idx >= len(price_df):
            continue

        buy_date = price_df.index[buy_idx]
        sell_date = price_df.index[sell_idx]

        buy_price = float(price_df.iloc[buy_idx]["Close"])
        ex_close = float(price_df.iloc[ex_idx]["Close"])
        sell_price = float(price_df.iloc[sell_idx]["Close"])

        if buy_price <= 0 or dividend <= 0:
            continue

        shares = capital_per_trade / buy_price
        gross_pnl = shares * ((sell_price - buy_price) + float(dividend))
        gross_return_pct = (gross_pnl / capital_per_trade) * 100.0
        drop_ratio = (buy_price - ex_close) / float(dividend)

        trades.append(
            TradeResult(
                ticker=ticker,
                ex_date=ex_date.strftime("%Y-%m-%d"),
                buy_date=buy_date.strftime("%Y-%m-%d"),
                sell_date=sell_date.strftime("%Y-%m-%d"),
                dividend=float(dividend),
                buy_price=buy_price,
                sell_price=sell_price,
                shares=shares,
                gross_pnl=gross_pnl,
                gross_return_pct=gross_return_pct,
                drop_ratio=drop_ratio,
            )
        )

    return trades


def summarize(trades_df: pd.DataFrame) -> None:
    if trades_df.empty:
        print("No trades found.")
        return

    total_trades = len(trades_df)
    wins = (trades_df["gross_pnl"] > 0).sum()
    losses = (trades_df["gross_pnl"] <= 0).sum()

    avg_return = trades_df["gross_return_pct"].mean()
    median_return = trades_df["gross_return_pct"].median()
    total_pnl = trades_df["gross_pnl"].sum()
    win_rate = wins / total_trades * 100.0
    avg_drop_ratio = trades_df["drop_ratio"].mean()
    median_drop_ratio = trades_df["drop_ratio"].median()

    print("\n=== SUMMARY ===")
    print(f"Trades:              {total_trades}")
    print(f"Wins:                {wins}")
    print(f"Losses:              {losses}")
    print(f"Win rate:            {win_rate:.2f}%")
    print(f"Average return:      {avg_return:.4f}%")
    print(f"Median return:       {median_return:.4f}%")
    print(f"Total gross PnL:     ${total_pnl:,.2f}")
    print(f"Avg drop ratio:      {avg_drop_ratio:.4f}")
    print(f"Median drop ratio:   {median_drop_ratio:.4f}")

    print("\n=== BY TICKER ===")
    by_ticker = (
        trades_df.groupby("ticker")
        .agg(
            trades=("ticker", "count"),
            avg_return_pct=("gross_return_pct", "mean"),
            median_return_pct=("gross_return_pct", "median"),
            avg_drop_ratio=("drop_ratio", "mean"),
            total_pnl=("gross_pnl", "sum"),
            win_rate_pct=("gross_pnl", lambda s: (s > 0).mean() * 100.0),
        )
        .sort_values("total_pnl", ascending=False)
    )
    print(by_ticker.round(4).to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="Ugly dividend capture backtest")
    parser.add_argument(
        "--tickers",
        nargs="+",
        required=True,
        help="Ticker list, e.g. KO PG JNJ XOM CVX",
    )
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-01-01")
    parser.add_argument("--hold-days", type=int, default=1, help="Sell N trading days after ex-date")
    parser.add_argument("--capital", type=float, default=10000.0, help="Capital per trade")
    parser.add_argument("--output-dir", required=True, help="Directory where results will be saved as hold_<N>.csv",)
    args = parser.parse_args()

    all_trades: List[TradeResult] = []

    for ticker in args.tickers:
        try:
            trades = backtest_ticker(
                ticker=ticker.upper(),
                start=args.start,
                end=args.end,
                hold_days=args.hold_days,
                capital_per_trade=args.capital,
            )
            all_trades.extend(trades)
            print(f"{ticker.upper()}: {len(trades)} trades")
        except Exception as e:
            print(f"{ticker.upper()}: ERROR -> {e}")

    trades_df = pd.DataFrame([asdict(t) for t in all_trades])

    if not trades_df.empty:
        from pathlib import Path

        trades_df = trades_df.sort_values(["ticker", "ex_date"]).reset_index(drop=True)

        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        save_path = output_dir / f"hold_{args.hold_days}.csv"
        trades_df.to_csv(save_path, index=False)

        print(f"\nSaved trades to {save_path}")

    summarize(trades_df)


if __name__ == "__main__":
    main()
