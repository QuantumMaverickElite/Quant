"""Reusable mechanics for the historical MarketState portfolio backtest."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtester.analytics.entropy import EntropyConfig, compute_entropy_metrics
from backtester.decision.entropy_decision import (
    apply_entropy_decision_columns,
    latest_entropy_decision,
)
from backtester.decision.market_state import build_market_state
from backtester.decision.market_state_features import build_rebalance_dates
from backtester.decision.volatility_decision import make_volatility_decision


def import_compute_garch_metrics():
    try:
        from backtester.analytics.garch import compute_garch_metrics

        return compute_garch_metrics
    except ImportError:
        pass

    try:
        from backtester.analytics.garch_metrics import compute_garch_metrics

        return compute_garch_metrics
    except ImportError:
        pass

    try:
        from backtester.analytics.volatility import compute_garch_metrics

        return compute_garch_metrics
    except ImportError:
        pass

    raise ImportError(
        "Could not import compute_garch_metrics. "
        "Check src/backtester/analytics and update this script."
    )


def compute_raw_momentum_score(prices: pd.DataFrame, asof_date: pd.Timestamp) -> float:
    close = prices.loc[:asof_date, "close"].dropna()

    if len(close) < 70:
        return 0.0

    ret_21 = close.iloc[-1] / close.iloc[-22] - 1.0
    ret_63 = close.iloc[-1] / close.iloc[-64] - 1.0

    raw_score = (0.40 * ret_21) + (0.60 * ret_63)

    return float(max(raw_score, 0.0))


def compute_market_state_for_date(
    prices: pd.DataFrame,
    asof_date: pd.Timestamp,
    entropy_config: EntropyConfig,
):
    compute_garch_metrics = import_compute_garch_metrics()

    hist = prices.loc[:asof_date].copy()

    if len(hist) < 320:
        raise ValueError("not enough history for entropy + volatility state")

    vol_price_series = hist[["close"]].copy()
    vol_metrics = compute_garch_metrics(vol_price_series)

    if vol_metrics.empty:
        raise ValueError("volatility metrics empty")

    latest_vol_row = vol_metrics.dropna().iloc[-1]
    volatility_decision = make_volatility_decision(latest_vol_row)

    entropy_metrics = compute_entropy_metrics(hist, entropy_config)
    entropy_metrics = apply_entropy_decision_columns(entropy_metrics)

    entropy_decision = latest_entropy_decision(entropy_metrics)

    market_state = build_market_state(
        entropy_decision=entropy_decision,
        volatility_decision=volatility_decision,
    )

    return volatility_decision, entropy_decision, market_state


def assign_weights(
    rows: list[dict],
    max_weight: float,
) -> pd.DataFrame:
    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df["target_weight"] = 0.0

    allowed = df["allow_new_equity_positions"] & (df["adjusted_score"] > 0)

    allowed_df = df.loc[allowed].copy()

    if allowed_df.empty:
        return df

    score_sum = allowed_df["adjusted_score"].sum()

    if score_sum <= 0:
        return df

    target_gross_exposure = float(
        np.clip(allowed_df["combined_multiplier"].mean(), 0.0, 1.0)
    )

    raw_weights = (allowed_df["adjusted_score"] / score_sum) * target_gross_exposure

    capped_weights = raw_weights.clip(upper=max_weight)

    df.loc[allowed_df.index, "target_weight"] = capped_weights

    return df


def compute_portfolio_returns(
    data: dict[str, pd.DataFrame],
    weights_by_date: dict[pd.Timestamp, dict[str, float]],
    bt_start: str,
    bt_end: str,
    capital: float,
) -> pd.DataFrame:
    close = pd.concat(
        {ticker: df["close"] for ticker, df in data.items()},
        axis=1,
    ).sort_index()

    close = close.ffill()

    returns = close.pct_change().fillna(0.0)

    bt_start_ts = pd.Timestamp(bt_start)
    bt_end_ts = pd.Timestamp(bt_end)

    returns = returns[(returns.index >= bt_start_ts) & (returns.index < bt_end_ts)]

    if returns.empty:
        raise ValueError("No returns available in backtest window.")

    weights = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=float)
    weights[:] = np.nan

    for date, weight_map in weights_by_date.items():
        if date in weights.index:
            for ticker, weight in weight_map.items():
                if ticker in weights.columns:
                    weights.loc[date, ticker] = weight

    weights = weights.ffill().fillna(0.0)

    portfolio_returns = (weights.shift(1).fillna(0.0) * returns).sum(axis=1)

    equity = capital * (1.0 + portfolio_returns).cumprod()

    out = pd.DataFrame(
        {
            "portfolio_return": portfolio_returns,
            "equity": equity,
        },
        index=returns.index,
    )

    return out


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def summarize_backtest(equity_curve: pd.DataFrame, capital: float) -> dict:
    start_equity = capital
    final_equity = float(equity_curve["equity"].iloc[-1])
    total_return = final_equity / start_equity - 1.0

    days = len(equity_curve)
    years = days / 252.0

    if years > 0:
        cagr = (final_equity / start_equity) ** (1.0 / years) - 1.0
    else:
        cagr = 0.0

    daily_returns = equity_curve["portfolio_return"]

    if daily_returns.std(ddof=0) > 0:
        sharpe = (daily_returns.mean() / daily_returns.std(ddof=0)) * np.sqrt(252)
    else:
        sharpe = 0.0

    return {
        "start_equity": start_equity,
        "final_equity": final_equity,
        "total_return_pct": total_return * 100,
        "cagr_pct": cagr * 100,
        "max_drawdown_pct": max_drawdown(equity_curve["equity"]) * 100,
        "sharpe": sharpe,
    }
