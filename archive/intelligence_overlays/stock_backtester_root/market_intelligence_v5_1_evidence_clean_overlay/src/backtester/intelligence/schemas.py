from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

Direction = Literal["bullish", "bearish", "neutral"]
Category = Literal[
    "company_fundamental",
    "sector_pressure",
    "macro_pressure",
    "political_risk",
    "valuation",
    "liquidity_flow",
    "technical_price_action",
    "unknown",
]
Horizon = Literal["intraday", "days", "days_to_weeks", "quarters", "unknown"]


@dataclass(slots=True)
class SourceDocument:
    source: str
    title: str
    text: str
    url: str | None = None
    published_at: str | None = None
    reliability: float = 0.60


@dataclass(slots=True)
class EvidenceClaim:
    entity: str
    claim: str
    category: Category
    direction: Direction
    magnitude: float
    reliability: float
    novelty: float
    time_horizon: Horizon
    source: str
    source_title: str | None = None
    source_url: str | None = None
    published_at: str | None = None
    event_id: str | None = None
    duplicate_count: int = 1
    independent_source_count: int = 1
    contradiction_count: int = 0
    trust_score: float | None = None
    source_diversity: float = 0.0
    orthogonal_weight: float = 1.0

    def weighted_impact(self) -> float:
        sign = 1.0 if self.direction == "bullish" else -1.0 if self.direction == "bearish" else 0.0
        trust = self.reliability if self.trust_score is None else self.trust_score
        return sign * self.magnitude * trust * (0.50 + 0.50 * self.novelty) * self.orthogonal_weight


@dataclass(slots=True)
class IntelligenceReport:
    query: str
    as_of: str
    sentiment_score: float
    regime_break_score: float
    confidence: float
    dominant_pressure: str
    time_horizon: str
    summary: str
    bullish_evidence: list[EvidenceClaim] = field(default_factory=list)
    bearish_evidence: list[EvidenceClaim] = field(default_factory=list)
    neutral_evidence: list[EvidenceClaim] = field(default_factory=list)
    model_features: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
