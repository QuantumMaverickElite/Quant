from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backtester.decision.volatility_decision import (
    VolatilityDecision,
    make_volatility_decision,
)


@dataclass(frozen=True)
class RegimeRoute:
    active_regime: str
    risk_multiplier: float
    preferred_strategy: str
    allow_mean_reversion: bool
    allow_breakout: bool
    allow_options: bool
    allow_new_equity_positions: bool
    reason: str


def route_market_state(row: pd.Series) -> RegimeRoute:
    """
    Convert market-state features into one strategy-facing route.

    For now, this router only uses the volatility decision layer.
    Later, this is where we will combine:
    - volatility regime
    - H-Vol pressure
    - correlation regime
    - entropy
    - ergodicity
    - liquidity state
    """

    vol_decision: VolatilityDecision = make_volatility_decision(row)

    return RegimeRoute(
        active_regime=vol_decision.vol_regime,
        risk_multiplier=vol_decision.risk_multiplier,
        preferred_strategy=vol_decision.preferred_strategy,
        allow_mean_reversion=vol_decision.allow_mean_reversion,
        allow_breakout=vol_decision.allow_breakout,
        allow_options=vol_decision.allow_options,
        allow_new_equity_positions=vol_decision.allow_new_equity_positions,
        reason=f"Volatility router selected {vol_decision.preferred_strategy}: {vol_decision.notes}",
    )


def add_regime_routes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add final regime-routing columns to a market-state DataFrame.
    """

    out = df.copy()

    routes = out.apply(route_market_state, axis=1)

    out["active_regime"] = [r.active_regime for r in routes]
    out["route_risk_multiplier"] = [r.risk_multiplier for r in routes]
    out["route_preferred_strategy"] = [r.preferred_strategy for r in routes]
    out["route_allow_mean_reversion"] = [r.allow_mean_reversion for r in routes]
    out["route_allow_breakout"] = [r.allow_breakout for r in routes]
    out["route_allow_options"] = [r.allow_options for r in routes]
    out["route_allow_new_equity_positions"] = [
        r.allow_new_equity_positions for r in routes
    ]
    out["route_reason"] = [r.reason for r in routes]

    return out
