from __future__ import annotations

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return float("nan")
    start = float(equity.iloc[0])
    end = float(equity.iloc[-1])
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0 or start <= 0:
        return float("nan")
    years = days / 365.25
    return (end / start) ** (1 / years) - 1


def annualized_vol(daily_returns: pd.Series) -> float:
    return float(daily_returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def sharpe(daily_returns: pd.Series, rf_annual: float = 0.0) -> float:
    # excess daily return assuming constant rf
    excess = daily_returns - (rf_annual / TRADING_DAYS)
    std = excess.std(ddof=1)
    if std == 0 or np.isnan(std):
        return float("nan")
    return float(np.sqrt(TRADING_DAYS) * excess.mean() / std)


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity / peak) - 1.0
    return float(dd.min())


def trade_stats(positions: pd.Series, strat_returns: pd.Series) -> dict:
    # a "trade" is a change in position (0->1 or 1->0)
    trades = int(positions.diff().abs().fillna(0).sum())

    # win rate: fraction of days with positive strategy return while in market
    active = positions.astype(bool)
    active_rets = strat_returns[active]
    win_rate = float((active_rets > 0).mean()) if len(active_rets) else float("nan")

    return {
        "trades": trades,
        "win_rate": win_rate,
    }


def summary(equity: pd.Series, daily_returns: pd.Series, positions: pd.Series) -> pd.DataFrame:
    stats = trade_stats(positions, daily_returns)

    out = {
        "CAGR": cagr(equity),
        "Vol (ann.)": annualized_vol(daily_returns),
        "Sharpe": sharpe(daily_returns),
        "Max Drawdown": max_drawdown(equity),
        "Trades": stats["trades"],
        "Win Rate (active days)": stats["win_rate"],
    }

    df = pd.DataFrame(out, index=["Strategy"]).T
    return df

