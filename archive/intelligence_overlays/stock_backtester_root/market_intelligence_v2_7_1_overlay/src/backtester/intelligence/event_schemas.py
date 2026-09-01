from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


EventDirection = Literal["bullish", "bearish", "mixed", "neutral"]
EventScope = Literal["ticker", "peer_group", "sector", "index", "macro", "political", "commodity", "unknown"]
EventHorizon = Literal["intraday", "days", "weeks", "quarters", "unknown"]


@dataclass(slots=True)
class MarketEvent:
    event_id: str
    query: str
    event_type: str
    scope: EventScope
    direction: EventDirection
    magnitude: float
    confidence: float
    novelty: float
    persistence: EventHorizon
    affected_entities: list[str]
    source: str
    source_title: str
    source_url: str | None
    published_at: str | None
    text: str
    cluster_id: str | None = None
    source_reliability: float = 0.55
    sentiment_model: str = "heuristic"
    event_classifier: str = "heuristic"
    event_type_confidence: float = 0.0
    scope_confidence: float = 0.0
    raw_semantic_scope: str | None = None

    def signed_impact(self) -> float:
        sign = 1.0 if self.direction == "bullish" else -1.0 if self.direction == "bearish" else 0.0
        if self.direction == "mixed":
            sign = 0.0
        return sign * self.magnitude * self.confidence * self.novelty * self.source_reliability

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
