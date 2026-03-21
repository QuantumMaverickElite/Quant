from __future__ import annotations

from dataclasses import asdict
from typing import List

import pandas as pd

from backtester.models.trade_result import DividendTrade
from backtester.utils import make_index_naive, get_trading_day_index


def run_dividend_capture_for_ticker(
    ticker: str,
    price_df: pd.DataFrame,
    dividends: pd.Series,
    start: str,
    end: str,
    hold_days: int,
    capital_per_trade: float,
) -> List[DividendTrade]:
    if price_df.empty:
        return []

    price_df = price_df[["Open", "High", "Low", "Close", "Volume"]].copy()
    price_df.index = make_index_naive(price_df.index)
    price_df = price_df.sort_index()

    if dividends is None or len(dividends) == 0:
        return []

    dividends = dividends.copy()
    dividends.index = make_index_naive(dividends.index)
    dividends = dividends.sort_index()
    dividends = dividends[
        (dividends.index >= pd.Timestamp(start)) &
        (dividends.index < pd.Timestamp(end))
    ]

    trades: List[DividendTrade] = []

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
            DividendTrade(
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


def dividend_trades_to_frame(trades: List[DividendTrade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()

    return pd.DataFrame([asdict(t) for t in trades]).sort_values(
        ["ticker", "ex_date"]
    ).reset_index(drop=True)
