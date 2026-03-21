import pandas as pd

from backtester.models.trade_result import BacktestResult


def run_backtest(close: pd.Series, positions: pd.Series, fee_bps: float) -> BacktestResult:
    rets = close.pct_change().fillna(0.0)

    trades = positions.diff().abs().fillna(0.0)
    fee = (fee_bps / 10_000.0) * trades

    strat_rets = positions * rets - fee
    equity = (1.0 + strat_rets).cumprod()

    return BacktestResult(equity=equity, returns=strat_rets, positions=positions)
