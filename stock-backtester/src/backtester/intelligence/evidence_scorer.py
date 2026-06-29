from __future__ import annotations

from collections import defaultdict
from statistics import mean

from .schemas import EvidenceClaim

FEATURE_KEYS = [
    "news_pressure",
    "macro_pressure",
    "sector_pressure",
    "idiosyncratic_pressure",
    "political_risk_pressure",
    "valuation_pressure",
]


def clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def aggregate_sentiment(claims: list[EvidenceClaim]) -> float:
    if not claims:
        return 0.0
    weighted = [claim.weighted_impact() for claim in claims]
    denom = (
        sum(
            (claim.trust_score if claim.trust_score is not None else claim.reliability)
            * (0.50 + 0.50 * claim.novelty)
            * claim.orthogonal_weight
            for claim in claims
        )
        or 1.0
    )
    return clamp(sum(weighted) / denom)


def pressure_features(claims: list[EvidenceClaim]) -> dict[str, float]:
    buckets: dict[str, list[float]] = defaultdict(list)

    for claim in claims:
        impact = claim.weighted_impact()
        buckets["news_pressure"].append(impact)

        if claim.category == "macro_pressure":
            buckets["macro_pressure"].append(impact)
        elif claim.category == "sector_pressure":
            buckets["sector_pressure"].append(impact)
        elif claim.category in {"company_fundamental", "technical_price_action"}:
            buckets["idiosyncratic_pressure"].append(impact)
        elif claim.category == "political_risk":
            buckets["political_risk_pressure"].append(impact)
        elif claim.category == "valuation":
            buckets["valuation_pressure"].append(impact)

    features = {}
    for key in FEATURE_KEYS:
        vals = buckets.get(key, [])
        features[key] = clamp(mean(vals)) if vals else 0.0
    return features


def confidence_score(claims: list[EvidenceClaim]) -> float:
    if not claims:
        return 0.0
    reliability = mean((claim.trust_score if claim.trust_score is not None else claim.reliability) for claim in claims)
    event_count = len({claim.event_id or id(claim) for claim in claims})
    evidence_count = min(1.0, event_count / 8.0)
    source_diversity = mean(claim.source_diversity for claim in claims)
    direction_strength = abs(aggregate_sentiment(claims))
    return max(
        0.0,
        min(1.0, 0.40 * reliability + 0.25 * evidence_count + 0.20 * direction_strength + 0.15 * source_diversity),
    )


def dominant_pressure(features: dict[str, float]) -> str:
    candidates = {key: abs(value) for key, value in features.items() if key.endswith("_pressure")}
    if not candidates:
        return "none"
    key = max(candidates, key=candidates.get)
    if candidates[key] < 0.05:
        return "none"
    return key
