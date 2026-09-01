"""Reusable construction helpers for MarketState feature matrices."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtester.analytics.entropy import EntropyConfig, compute_entropy_metrics
from backtester.analytics.fast_volatility import compute_fast_volatility_metrics
from backtester.decision.entropy_decision import (
    EntropyDecision,
    apply_entropy_decision_columns,
)
from backtester.decision.market_state import build_market_state
from backtester.decision.volatility_decision import make_volatility_decision


def build_rebalance_dates(
    trading_index: pd.DatetimeIndex,
    bt_start: str,
    bt_end: str,
    freq: str,
) -> list[pd.Timestamp]:
    bt_start_ts = pd.Timestamp(bt_start)
    bt_end_ts = pd.Timestamp(bt_end)

    eligible = trading_index[
        (trading_index >= bt_start_ts) & (trading_index < bt_end_ts)
    ]

    if eligible.empty:
        return []

    if freq == "D":
        return [pd.Timestamp(date) for date in eligible]

    if freq in {"W", "B", "3W", "6W"}:
        weekly_groups = pd.Series(eligible, index=eligible).groupby(
            [eligible.year, eligible.isocalendar().week]
        )
        weekly_dates = [pd.Timestamp(group.iloc[0]) for _, group in weekly_groups]

        step_by_freq = {
            "W": 1,
            "B": 2,
            "3W": 3,
            "6W": 6,
        }
        step = step_by_freq[freq]

        return weekly_dates[::step]

    if freq == "M":
        groups = pd.Series(eligible, index=eligible).groupby(
            [eligible.year, eligible.month]
        )
    elif freq == "Q":
        groups = pd.Series(eligible, index=eligible).groupby(
            [eligible.year, eligible.quarter]
        )
    else:
        raise ValueError(f"Unsupported rebalance frequency: {freq}")

    # Rebalance on the first trading day of each calendar period.
    return [pd.Timestamp(group.iloc[0]) for _, group in groups]


def compute_raw_momentum_scores(prices: pd.DataFrame) -> pd.Series:
    close = prices["close"].astype(float)

    ret_21 = close / close.shift(21) - 1.0
    ret_63 = close / close.shift(63) - 1.0

    raw = (0.40 * ret_21) + (0.60 * ret_63)
    raw = raw.clip(lower=0.0)

    return raw


def entropy_decision_from_row(row: pd.Series) -> EntropyDecision:
    entropy_regime = row.get("entropy_regime", "UNKNOWN")
    direction_entropy_regime = row.get("direction_entropy_regime", "UNKNOWN")
    entropy_state = row.get("entropy_state", "UNKNOWN")
    entropy_state_description = row.get(
        "entropy_state_description",
        "No entropy state description available.",
    )

    normalized_entropy = row.get("normalized_entropy", float("nan"))
    entropy_zscore = row.get("entropy_zscore", float("nan"))
    entropy_percentile = row.get("entropy_percentile", float("nan"))

    normalized_direction_entropy = row.get("normalized_direction_entropy", float("nan"))
    direction_entropy_zscore = row.get("direction_entropy_zscore", float("nan"))
    direction_entropy_percentile = row.get("direction_entropy_percentile", float("nan"))

    signal_trust_multiplier = row.get("signal_trust_multiplier", 1.0)

    reason = (
        f"entropy_state={entropy_state}, "
        f"return_entropy_regime={entropy_regime}, "
        f"direction_entropy_regime={direction_entropy_regime}, "
        f"signal_trust_multiplier={signal_trust_multiplier:.2f}"
    )

    return EntropyDecision(
        entropy_regime=entropy_regime,
        direction_entropy_regime=direction_entropy_regime,
        entropy_state=entropy_state,
        entropy_state_description=entropy_state_description,
        normalized_entropy=normalized_entropy,
        entropy_zscore=entropy_zscore,
        entropy_percentile=entropy_percentile,
        normalized_direction_entropy=normalized_direction_entropy,
        direction_entropy_zscore=direction_entropy_zscore,
        direction_entropy_percentile=direction_entropy_percentile,
        signal_trust_multiplier=signal_trust_multiplier,
        allow_new_signals=True,
        reason=reason,
    )


def build_feature_rows_for_ticker(
    ticker: str,
    prices: pd.DataFrame,
    rebalance_dates: list[pd.Timestamp],
    entropy_config: EntropyConfig,
    zscore_window: int,
) -> list[dict]:
    rows = []

    close = prices["close"].dropna()

    if close.empty:
        return rows

    raw_scores = compute_raw_momentum_scores(prices)

    vol_metrics = compute_fast_volatility_metrics(
        prices[["close"]],
        price_col="close",
        zscore_window=zscore_window,
    )

    entropy_metrics = compute_entropy_metrics(prices, entropy_config)
    entropy_metrics = apply_entropy_decision_columns(entropy_metrics)

    combined_index = prices.index.intersection(vol_metrics.index).intersection(
        entropy_metrics.index
    )

    prices = prices.loc[combined_index]
    vol_metrics = vol_metrics.loc[combined_index]
    entropy_metrics = entropy_metrics.loc[combined_index]
    raw_scores = raw_scores.loc[combined_index]

    for date in rebalance_dates:
        hist_idx = combined_index[combined_index <= date]

        if hist_idx.empty:
            continue

        asof_date = hist_idx[-1]

        vol_row = vol_metrics.loc[asof_date]
        ent_row = entropy_metrics.loc[asof_date]

        if pd.isna(vol_row.get("vol_percentile", np.nan)):
            continue

        if pd.isna(ent_row.get("entropy_percentile", np.nan)):
            continue

        if pd.isna(ent_row.get("direction_entropy_percentile", np.nan)):
            continue

        volatility_decision = make_volatility_decision(vol_row)
        entropy_decision = entropy_decision_from_row(ent_row)

        market_state = build_market_state(
            entropy_decision=entropy_decision,
            volatility_decision=volatility_decision,
        )

        raw_score = float(raw_scores.loc[asof_date])

        if not np.isfinite(raw_score):
            raw_score = 0.0

        if not market_state.allow_new_equity_positions:
            adjusted_score = 0.0
        else:
            adjusted_score = raw_score * market_state.combined_multiplier

        rows.append(
            {
                "date": pd.Timestamp(date),
                "asof_date": pd.Timestamp(asof_date),
                "ticker": ticker,
                "close": float(prices.loc[asof_date, "close"]),
                "raw_score": raw_score,
                "adjusted_score": adjusted_score,
                "vol_regime": market_state.volatility_regime,
                "return_entropy_regime": market_state.return_entropy_regime,
                "direction_entropy_regime": market_state.direction_entropy_regime,
                "entropy_state": market_state.entropy_state,
                "risk_multiplier": market_state.risk_multiplier,
                "signal_trust_multiplier": market_state.signal_trust_multiplier,
                "combined_multiplier": market_state.combined_multiplier,
                "allow_new_equity_positions": market_state.allow_new_equity_positions,
                "allow_options": market_state.allow_options,
                "capital_posture": market_state.capital_posture,
                "preferred_strategy": market_state.preferred_strategy,
                "vol_percentile": vol_row.get("vol_percentile", np.nan),
                "vol_zscore": vol_row.get("vol_zscore", np.nan),
                "entropy_percentile": ent_row.get("entropy_percentile", np.nan),
                "direction_entropy_percentile": ent_row.get(
                    "direction_entropy_percentile", np.nan
                ),
            }
        )

    return rows
