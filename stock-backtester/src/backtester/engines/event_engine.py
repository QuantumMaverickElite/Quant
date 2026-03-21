from typing import List

import pandas as pd

from backtester.data import fetch_ohlcv, fetch_dividends
from backtester.models.trade_result import DividendTrade
from backtester.strategies.event_strategies import (
    run_dividend_capture_for_ticker,
    dividend_trades_to_frame,
)


def run_dividend_strategy(
    tickers: List[str],
    start: str,
    end: str,
    hold_days: int,
    capital_per_trade: float,
) -> pd.DataFrame:
    all_trades: List[DividendTrade] = []

    for ticker in tickers:
        try:
            price_df = fetch_ohlcv(ticker, start, end)
            dividends = fetch_dividends(ticker, start, end)

            trades = run_dividend_capture_for_ticker(
                ticker=ticker,
                price_df=price_df,
                dividends=dividends,
                start=start,
                end=end,
                hold_days=hold_days,
                capital_per_trade=capital_per_trade,
            )

            all_trades.extend(trades)
            print(f"{ticker}: {len(trades)} trades")

        except Exception as e:
            print(f"{ticker}: ERROR -> {e}")

    return dividend_trades_to_frame(all_trades)

def summarize_dividend_trades(trades_df: pd.DataFrame) -> pd.DataFrame:
    if trades_df.empty:
        return pd.DataFrame()

    total_trades = len(trades_df)
    wins = (trades_df["gross_pnl"] > 0).sum()

    summary = {
        "Trades": total_trades,
        "Win Rate %": (wins / total_trades) * 100,
        "Avg Return %": trades_df["gross_return_pct"].mean(),
        "Median Return %": trades_df["gross_return_pct"].median(),
        "Total PnL": trades_df["gross_pnl"].sum(),
    }

    return pd.DataFrame([summary])
