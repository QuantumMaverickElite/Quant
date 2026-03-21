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
