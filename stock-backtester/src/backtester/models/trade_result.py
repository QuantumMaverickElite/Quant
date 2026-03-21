from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class BacktestResult:
    equity: pd.Series
    returns: pd.Series
    positions: pd.Series


@dataclass(frozen=True)
class DividendTrade:
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
