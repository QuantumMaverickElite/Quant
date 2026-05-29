from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backtester.decision.entropy_decision import EntropyDecision


@dataclass(frozen=True)
class MarketState:
    volatility_regime: str
    entropy_state: str
    return_entropy_regime: str
    direction_entropy_regime: str

    risk_multiplier: float
    signal_trust_multiplier: float
    combined_multiplier: float

    allow_new_equity_positions: bool
    allow_new_signals: bool
    allow_options: bool

    preferred_strategy: str | None
    capital_posture: str
    reason: str


def _safe_get(obj: Any, *names: str, default: Any = None) -> Any:
    """
    Read a field from either a dataclass/object or dictionary.
    This keeps MarketState flexible while your volatility engine evolves.
    """
    if obj is None:
        return default

    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
        return default

    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)

    return default


def classify_capital_posture(
    volatility_regime: str,
    entropy_state: str,
    combined_multiplier: float,
    allow_new_equity_positions: bool,
    allow_new_signals: bool,
) -> str:
    if not allow_new_equity_positions or not allow_new_signals:
        return "RESTRICTED"

    if volatility_regime == "EXTREME":
        return "CAPITAL_PRESERVATION"

    if "EXTREME" in entropy_state and combined_multiplier <= 0.50:
        return "CAPITAL_PRESERVATION"

    if combined_multiplier < 0.50:
        return "CAPITAL_PRESERVATION"

    if combined_multiplier < 0.75:
        return "DEFENSIVE"

    if combined_multiplier < 1.00:
        return "CAUTIOUS"

    if combined_multiplier > 1.00:
        return "EXPANSIVE"

    return "NORMAL"


def build_market_state(
    entropy_decision: EntropyDecision,
    volatility_decision: Any | None = None,
) -> MarketState:
    """
    Combine entropy and volatility decisions into one allocator-facing object.

    Entropy controls signal trust.
    Volatility controls risk sizing.
    The allocator will eventually consume this object directly.
    """

    volatility_regime = _safe_get(
        volatility_decision,
        "volatility_regime",
        "vol_regime",
        "regime",
        default="UNKNOWN",
    )

    risk_multiplier = float(
        _safe_get(
            volatility_decision,
            "risk_multiplier",
            "volatility_risk_multiplier",
            default=1.0,
        )
    )

    allow_new_equity_positions = bool(
        _safe_get(
            volatility_decision,
            "allow_new_equity_positions",
            "allow_equity",
            default=True,
        )
    )

    allow_options = bool(
        _safe_get(
            volatility_decision,
            "allow_options",
            default=False,
        )
    )

    preferred_strategy = _safe_get(
        volatility_decision,
        "preferred_strategy",
        default=None,
    )

    signal_trust_multiplier = float(entropy_decision.signal_trust_multiplier)

    combined_multiplier = risk_multiplier * signal_trust_multiplier

    capital_posture = classify_capital_posture(
        volatility_regime=volatility_regime,
        entropy_state=entropy_decision.entropy_state,
        combined_multiplier=combined_multiplier,
        allow_new_equity_positions=allow_new_equity_positions,
        allow_new_signals=entropy_decision.allow_new_signals,
    )

    reason = (
        f"volatility_regime={volatility_regime}, "
        f"entropy_state={entropy_decision.entropy_state}, "
        f"risk_multiplier={risk_multiplier:.2f}, "
        f"signal_trust_multiplier={signal_trust_multiplier:.2f}, "
        f"combined_multiplier={combined_multiplier:.2f}, "
        f"capital_posture={capital_posture}"
    )

    return MarketState(
        volatility_regime=volatility_regime,
        entropy_state=entropy_decision.entropy_state,
        return_entropy_regime=entropy_decision.entropy_regime,
        direction_entropy_regime=entropy_decision.direction_entropy_regime,
        risk_multiplier=risk_multiplier,
        signal_trust_multiplier=signal_trust_multiplier,
        combined_multiplier=combined_multiplier,
        allow_new_equity_positions=allow_new_equity_positions,
        allow_new_signals=entropy_decision.allow_new_signals,
        allow_options=allow_options,
        preferred_strategy=preferred_strategy,
        capital_posture=capital_posture,
        reason=reason,
    )
