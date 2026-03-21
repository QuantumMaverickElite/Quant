from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class BacktestResult:
    equity: pd.Series
    returns: pd.Series
    positions: pd.Series
