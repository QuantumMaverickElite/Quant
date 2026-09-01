from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from statistics import mean

from .schemas import EvidenceClaim


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "said",
    "says",
    "that",
    "the",
    "this",
    "to",
    "with",
}

OFFICIAL_SOURCE_TERMS = (
    "sec",
    "edgar",
    "investor relations",
    "federal reserve",
    "treasury",
    "bls",
    "bea",
)
SOCIAL_SOURCE_TERMS = ("reddit", "x", "twitter", "stocktwits", "instagram")
DENIAL_TERMS = ("false", "not real", "no contract", "denied", "unconfirmed", "fake")
POSITIVE_EVENT_TERMS = ("contract", "agreement", "win", "wins", "announced", "disclosed", "raised", "beat", "upgrade")


@dataclass(slots=True)
class EvidenceEvent:
    event_id: str
    entity: str
    category: str
    direction: str
    representative_claim: str
    claims: list[EvidenceClaim] = field(default_factory=list)
    trust_score: float = 0.0
    source_diversity: float = 0.0
    duplicate_count: int = 0
    independent_source_count: int = 0
    contradiction_count: int = 0
    official_confirmation: bool = False
    social_only: bool = False
    orthogonal_event_weight: float = 1.0

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "entity": self.entity,
            "category": self.category,
            "direction": self.direction,
            "representative_claim": self.representative_claim,
            "trust_score": round(self.trust_score, 4),
            "source_diversity": round(self.source_diversity, 4),
            "duplicate_count": self.duplicate_count,
            "independent_source_count": self.independent_source_count,
            "contradiction_count": self.contradiction_count,
            "official_confirmation": self.official_confirmation,
            "social_only": self.social_only,
            "orthogonal_event_weight": round(self.orthogonal_event_weight, 4),
            "sources": sorted({claim.source for claim in self.claims}),
        }


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9$.-]{1,}", text.lower())
    return {word.strip("$.-") for word in words if word not in STOPWORDS and len(word) > 2}


def similarity(left: str, right: str) -> float:
    a = tokenize(left)
    b = tokenize(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def canonical_source(source: str) -> str:
    source = re.sub(r"https?://", "", source.lower().strip())
    source = re.sub(r"^www\.", "", source)
    source = source.split("/")[0]
    source = re.sub(r"[^a-z0-9. -]+", " ", source)
    return re.sub(r"\s+", " ", source).strip() or "unknown"


def is_official_source(source: str) -> bool:
    source_lower = source.lower()
    return any(term in source_lower for term in OFFICIAL_SOURCE_TERMS)


def is_social_source(source: str) -> bool:
    source_lower = source.lower()
    return any(term in source_lower for term in SOCIAL_SOURCE_TERMS)


def make_event_id(claim: EvidenceClaim, index: int) -> str:
    text = " ".join(sorted(tokenize(claim.claim)))[:160]
    payload = f"{claim.entity}|{claim.category}|{claim.direction}|{text}|{index}"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
    return f"{claim.entity}_{claim.category}_{claim.direction}_{digest}"


def should_join_event(claim: EvidenceClaim, event: EvidenceEvent, threshold: float) -> bool:
    if claim.entity != event.entity:
        return False
    if claim.category != event.category:
        return False
    if claim.direction != event.direction:
        return False
    score = similarity(claim.claim, event.representative_claim)
    if score >= threshold:
        return True
    claim_tokens = tokenize(claim.claim)
    event_tokens = tokenize(event.representative_claim)
    if not claim_tokens or not event_tokens:
        return False
    smaller = min(len(claim_tokens), len(event_tokens))
    overlap = len(claim_tokens & event_tokens) / max(1, smaller)
    return overlap >= 0.72


def has_any_term(text: str, terms: tuple[str, ...]) -> bool:
    text_lower = text.lower()
    return any(term in text_lower for term in terms)


def looks_like_denial_conflict(left: str, right: str) -> bool:
    left_denies = has_any_term(left, DENIAL_TERMS)
    right_denies = has_any_term(right, DENIAL_TERMS)
    if left_denies == right_denies:
        return False
    return has_any_term(left, POSITIVE_EVENT_TERMS) and has_any_term(right, POSITIVE_EVENT_TERMS)


def cluster_claims(claims: list[EvidenceClaim], *, similarity_threshold: float = 0.48) -> list[EvidenceEvent]:
    events: list[EvidenceEvent] = []
    for claim in claims:
        matched = None
        for event in events:
            if should_join_event(claim, event, similarity_threshold):
                matched = event
                break
        if matched is None:
            matched = EvidenceEvent(
                event_id=make_event_id(claim, len(events)),
                entity=claim.entity,
                category=claim.category,
                direction=claim.direction,
                representative_claim=claim.claim,
            )
            events.append(matched)
        matched.claims.append(claim)
    return events


def annotate_contradictions(events: list[EvidenceEvent], *, threshold: float = 0.32) -> None:
    for event in events:
        contradictions = 0
        for other in events:
            if event is other:
                continue
            if event.entity != other.entity or event.category != other.category:
                continue
            if event.direction == other.direction or "neutral" in {event.direction, other.direction}:
                continue
            if similarity(event.representative_claim, other.representative_claim) >= threshold or looks_like_denial_conflict(
                event.representative_claim, other.representative_claim
            ):
                contradictions += 1
        event.contradiction_count = contradictions


def score_event(event: EvidenceEvent) -> None:
    sources = {canonical_source(claim.source) for claim in event.claims}
    event.duplicate_count = len(event.claims)
    event.independent_source_count = len(sources)
    event.source_diversity = clamp(math.log1p(event.independent_source_count) / math.log1p(5))
    duplicate_support = clamp(math.log1p(event.duplicate_count) / math.log1p(8))
    event.official_confirmation = any(is_official_source(claim.source) or claim.reliability >= 0.88 for claim in event.claims)
    event.social_only = all(is_social_source(claim.source) for claim in event.claims)
    avg_reliability = mean(claim.reliability for claim in event.claims)
    contradiction_penalty = clamp(event.contradiction_count / 3.0)

    event.trust_score = clamp(
        0.45 * avg_reliability
        + 0.20 * event.source_diversity
        + 0.15 * duplicate_support
        + (0.15 if event.official_confirmation else 0.0)
        - 0.20 * contradiction_penalty
        - (0.10 if event.social_only else 0.0)
    )
    event.orthogonal_event_weight = clamp(
        1.00
        + 0.25 * event.source_diversity
        + (0.20 if event.official_confirmation else 0.0)
        - 0.30 * contradiction_penalty,
        0.35,
        1.35,
    )


def orthogonalize_claims(claims: list[EvidenceClaim]) -> tuple[list[EvidenceClaim], list[EvidenceEvent]]:
    events = cluster_claims(claims)
    annotate_contradictions(events)
    for event in events:
        score_event(event)
        per_claim_weight = event.orthogonal_event_weight / max(1, len(event.claims))
        for claim in event.claims:
            claim.event_id = event.event_id
            claim.duplicate_count = event.duplicate_count
            claim.independent_source_count = event.independent_source_count
            claim.contradiction_count = event.contradiction_count
            claim.trust_score = event.trust_score
            claim.source_diversity = event.source_diversity
            claim.orthogonal_weight = per_claim_weight
            claim.reliability = event.trust_score
    return claims, events


def evidence_graph_features(events: list[EvidenceEvent], raw_claim_count: int | None = None) -> dict[str, float]:
    if raw_claim_count is None:
        raw_claim_count = sum(len(event.claims) for event in events)
    if not events:
        return {
            "raw_claim_count": float(raw_claim_count or 0),
            "orthogonal_event_count": 0.0,
            "duplicate_claim_count": 0.0,
            "avg_event_trust": 0.0,
            "avg_source_diversity": 0.0,
            "contradiction_event_count": 0.0,
            "official_confirmed_event_count": 0.0,
            "social_only_event_count": 0.0,
        }
    return {
        "raw_claim_count": float(raw_claim_count),
        "orthogonal_event_count": float(len(events)),
        "duplicate_claim_count": float(max(0, raw_claim_count - len(events))),
        "avg_event_trust": mean(event.trust_score for event in events),
        "avg_source_diversity": mean(event.source_diversity for event in events),
        "contradiction_event_count": float(sum(1 for event in events if event.contradiction_count > 0)),
        "official_confirmed_event_count": float(sum(1 for event in events if event.official_confirmation)),
        "social_only_event_count": float(sum(1 for event in events if event.social_only)),
    }
