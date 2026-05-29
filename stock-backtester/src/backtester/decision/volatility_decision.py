from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

VolRegime = Literal["LOW", "NORMAL", "HIGH", "EXTREME"]


@dataclass(frozen=True)
class VolatilityDecision:
    vol_regime: str
    risk_multiplier: float
    preferred_strategy: str
    allow_mean_reversion: bool
    allow_breakout: bool
    allow_options: bool
    allow_new_equity_positions: bool
    notes: str


def classify_extreme_regime(row: pd.Series) -> str:
    """
    Upgrade HIGH volatility into EXTREME when volatility conditions are severe.
    """

    regime = str(row.get("vol_regime", "NORMAL")).upper()
    z = float(row.get("vol_zscore", 0.0))
    percentile = float(row.get("vol_percentile", 0.0))
    spike = bool(row.get("vol_spike_flag", False))

    if z >= 2.5 or percentile >= 0.95 or spike:
        return "EXTREME"

    return regime


def make_volatility_decision(row: pd.Series) -> VolatilityDecision:
    """
    Convert a GARCH volatility state row into a strategy-facing decision.
    """

    regime = classify_extreme_regime(row)

    if regime == "LOW":
        return VolatilityDecision(
            vol_regime=regime,
            risk_multiplier=1.00,
            preferred_strategy="mean_reversion",
            allow_mean_reversion=True,
            allow_breakout=False,
            allow_options=False,
            allow_new_equity_positions=True,
            notes="Low volatility: no router intervention in extreme-only experiment.",
        )

    if regime == "NORMAL":
        return VolatilityDecision(
            vol_regime=regime,
            risk_multiplier=1.00,
            preferred_strategy="standard",
            allow_mean_reversion=True,
            allow_breakout=True,
            allow_options=False,
            allow_new_equity_positions=True,
            notes="Normal volatility: allow standard strategy behavior.",
        )

    if regime == "HIGH":
        return VolatilityDecision(
            vol_regime=regime,
            risk_multiplier=1.00,
            preferred_strategy="breakout",
            allow_mean_reversion=False,
            allow_breakout=True,
            allow_options=True,
            allow_new_equity_positions=True,
            notes="High volatility: no equity scaling in extreme-only experiment; options logic may still be allowed.",
        )

    if regime == "EXTREME":
        return VolatilityDecision(
            vol_regime=regime,
            risk_multiplier=0.50,
            preferred_strategy="defensive_or_long_vol",
            allow_mean_reversion=False,
            allow_breakout=False,
            allow_options=True,
            allow_new_equity_positions=False,
            notes="Extreme volatility: reduce directional equity exposure as a risk override.",
        )

    return VolatilityDecision(
        vol_regime="UNKNOWN",
        risk_multiplier=0.50,
        preferred_strategy="defensive",
        allow_mean_reversion=False,
        allow_breakout=False,
        allow_options=False,
        allow_new_equity_positions=False,
        notes="Unknown volatility state: default to defensive behavior.",
    )


def add_volatility_decisions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add volatility decision columns to a full GARCH metrics DataFrame.
    """

    out = df.copy()

    decisions = out.apply(make_volatility_decision, axis=1)

    out["decision_vol_regime"] = [d.vol_regime for d in decisions]
    out["risk_multiplier"] = [d.risk_multiplier for d in decisions]
    out["preferred_strategy"] = [d.preferred_strategy for d in decisions]
    out["allow_mean_reversion"] = [d.allow_mean_reversion for d in decisions]
    out["allow_breakout"] = [d.allow_breakout for d in decisions]
    out["allow_options"] = [d.allow_options for d in decisions]
    out["allow_new_equity_positions"] = [
        d.allow_new_equity_positions for d in decisions
    ]
    out["decision_notes"] = [d.notes for d in decisions]

    return out
