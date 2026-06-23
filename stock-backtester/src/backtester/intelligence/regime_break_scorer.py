from __future__ import annotations

from .schemas import EvidenceClaim


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def negative_component(x: float) -> float:
    return clamp01(-x)


def novelty_risk(claims: list[EvidenceClaim]) -> float:
    bearish = [claim for claim in claims if claim.direction == "bearish"]
    if not bearish:
        return 0.0
    return clamp01(sum(claim.magnitude * claim.novelty * claim.reliability for claim in bearish) / max(1, len(bearish)))


def company_specific_risk(claims: list[EvidenceClaim]) -> float:
    specific = [
        claim
        for claim in claims
        if claim.direction == "bearish" and claim.category in {"company_fundamental", "technical_price_action"}
    ]
    if not specific:
        return 0.0
    return clamp01(sum(claim.magnitude * claim.reliability for claim in specific) / max(1, len(specific)))


def regime_break_score(
    claims: list[EvidenceClaim],
    features: dict[str, float],
    *,
    peer_divergence: float = 0.0,
    volume_shock: float = 0.0,
    trend_damage: float = 0.0,
) -> float:
    """Return [0,1]. Higher means the old amplitude envelope is more likely damaged.

    Price action is intentionally given enough weight to force caution even when
    headlines are mixed. If a stock is badly underperforming peers, trading on
    abnormal volume, or losing trend structure, that is evidence by itself.
    """
    idio = max(company_specific_risk(claims), negative_component(features.get("idiosyncratic_pressure", 0.0)))
    novelty = novelty_risk(claims)
    macro = negative_component(features.get("macro_pressure", 0.0))
    sector = negative_component(features.get("sector_pressure", 0.0))
    political = negative_component(features.get("political_risk_pressure", 0.0))
    valuation = negative_component(features.get("valuation_pressure", 0.0))
    peer = clamp01(peer_divergence)
    volume = clamp01(volume_shock)
    trend = clamp01(trend_damage)

    price_action_risk = clamp01(0.35 * peer + 0.25 * volume + 0.40 * trend)

    score = (
        0.28 * price_action_risk
        + 0.24 * idio
        + 0.16 * novelty
        + 0.10 * macro
        + 0.08 * sector
        + 0.06 * political
        + 0.04 * valuation
        + 0.04 * max(peer, volume, trend)
    )
    if price_action_risk >= 0.35 or trend >= 0.75:
        price_floor = 0.30 + 0.20 * max(price_action_risk - 0.35, trend - 0.75, 0.0)
        score = max(score, price_floor)
    return clamp01(score)


def price_action_risk_score(
    *,
    peer_divergence: float = 0.0,
    volume_shock: float = 0.0,
    trend_damage: float = 0.0,
) -> float:
    peer = clamp01(peer_divergence)
    volume = clamp01(volume_shock)
    trend = clamp01(trend_damage)
    return clamp01(0.35 * peer + 0.25 * volume + 0.40 * trend)


def regime_action(score: float) -> str:
    if score < 0.30:
        return "same_regime_scale_in_allowed"
    if score < 0.55:
        return "caution_hold_no_adding"
    if score < 0.75:
        return "likely_regime_damage_do_not_average_down"
    return "thesis_break_risk_reduce_or_wait"
