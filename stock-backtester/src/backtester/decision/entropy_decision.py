from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class EntropyDecision:
    entropy_regime: str
    direction_entropy_regime: str
    entropy_state: str
    entropy_state_description: str

    normalized_entropy: float
    entropy_zscore: float
    entropy_percentile: float

    normalized_direction_entropy: float
    direction_entropy_zscore: float
    direction_entropy_percentile: float

    signal_trust_multiplier: float
    allow_new_signals: bool
    reason: str


def classify_entropy_regime(percentile: float) -> str:
    if pd.isna(percentile):
        return "UNKNOWN"

    if percentile < 0.25:
        return "LOW"
    if percentile < 0.75:
        return "NORMAL"
    if percentile < 0.90:
        return "HIGH"
    return "EXTREME"


def trust_multiplier_for_regime(regime: str) -> float:
    mapping = {
        "LOW": 1.10,
        "NORMAL": 1.00,
        "HIGH": 0.75,
        "EXTREME": 0.50,
        "UNKNOWN": 1.00,
    }
    return mapping.get(regime, 1.00)


def combine_trust_multipliers(
    return_entropy_regime: str,
    direction_entropy_regime: str,
) -> float:
    """
    Conservative v1 rule:
    use the more cautious multiplier between return entropy and direction entropy.
    """
    return_mult = trust_multiplier_for_regime(return_entropy_regime)
    direction_mult = trust_multiplier_for_regime(direction_entropy_regime)

    return min(return_mult, direction_mult)


def build_entropy_state(
    return_entropy_regime: str,
    direction_entropy_regime: str,
) -> str:
    return f"RETURN_{return_entropy_regime}_DIRECTION_{direction_entropy_regime}"


def describe_entropy_state(
    return_entropy_regime: str,
    direction_entropy_regime: str,
) -> str:
    if "UNKNOWN" in {return_entropy_regime, direction_entropy_regime}:
        return "Insufficient entropy history to classify market disorder."

    if return_entropy_regime in {"LOW", "NORMAL"} and direction_entropy_regime in {
        "LOW",
        "NORMAL",
    }:
        return (
            "Entropy conditions are stable. Return dispersion and directional "
            "flipping are not unusually chaotic."
        )

    if return_entropy_regime in {"HIGH", "EXTREME"} and direction_entropy_regime in {
        "LOW",
        "NORMAL",
    }:
        return (
            "Return sizes are unusually dispersed, but directional movement is "
            "not unusually choppy. Treat signals with caution, but this is not "
            "necessarily directional chaos."
        )

    if return_entropy_regime in {"LOW", "NORMAL"} and direction_entropy_regime in {
        "HIGH",
        "EXTREME",
    }:
        return (
            "Return sizes are not unusually dispersed, but the up/down sequence "
            "is unusually choppy. Trend-following signals may be less reliable."
        )

    if return_entropy_regime in {"HIGH", "EXTREME"} and direction_entropy_regime in {
        "HIGH",
        "EXTREME",
    }:
        return (
            "Both return dispersion and directional flipping are unusually high. "
            "This is a noisy/chaotic entropy state; reduce signal trust heavily."
        )

    return "Mixed entropy state. Use the combined trust multiplier for caution."


def apply_entropy_decision_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["entropy_regime"] = out["entropy_percentile"].apply(classify_entropy_regime)

    out["direction_entropy_regime"] = out["direction_entropy_percentile"].apply(
        classify_entropy_regime
    )

    out["entropy_state"] = [
        build_entropy_state(return_regime, direction_regime)
        for return_regime, direction_regime in zip(
            out["entropy_regime"],
            out["direction_entropy_regime"],
        )
    ]

    out["entropy_state_description"] = [
        describe_entropy_state(return_regime, direction_regime)
        for return_regime, direction_regime in zip(
            out["entropy_regime"],
            out["direction_entropy_regime"],
        )
    ]

    out["signal_trust_multiplier"] = [
        combine_trust_multipliers(return_regime, direction_regime)
        for return_regime, direction_regime in zip(
            out["entropy_regime"],
            out["direction_entropy_regime"],
        )
    ]

    return out


def latest_entropy_decision(df: pd.DataFrame) -> EntropyDecision:
    if df.empty:
        raise ValueError("DataFrame is empty.")

    last = df.iloc[-1]

    entropy_regime = last.get("entropy_regime", "UNKNOWN")
    direction_entropy_regime = last.get("direction_entropy_regime", "UNKNOWN")
    entropy_state = last.get("entropy_state", "UNKNOWN")
    entropy_state_description = last.get(
        "entropy_state_description",
        "No entropy state description available.",
    )

    normalized_entropy = last.get("normalized_entropy", float("nan"))
    entropy_zscore = last.get("entropy_zscore", float("nan"))
    entropy_percentile = last.get("entropy_percentile", float("nan"))

    normalized_direction_entropy = last.get(
        "normalized_direction_entropy", float("nan")
    )
    direction_entropy_zscore = last.get("direction_entropy_zscore", float("nan"))
    direction_entropy_percentile = last.get(
        "direction_entropy_percentile", float("nan")
    )

    signal_trust_multiplier = last.get("signal_trust_multiplier", 1.0)

    allow_new_signals = True

    reason = (
        f"entropy_state={entropy_state}, "
        f"return_entropy_regime={entropy_regime}, "
        f"direction_entropy_regime={direction_entropy_regime}, "
        f"normalized_entropy={normalized_entropy:.4f}, "
        f"entropy_percentile={entropy_percentile:.4f}, "
        f"normalized_direction_entropy={normalized_direction_entropy:.4f}, "
        f"direction_entropy_percentile={direction_entropy_percentile:.4f}, "
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
        allow_new_signals=allow_new_signals,
        reason=reason,
    )
