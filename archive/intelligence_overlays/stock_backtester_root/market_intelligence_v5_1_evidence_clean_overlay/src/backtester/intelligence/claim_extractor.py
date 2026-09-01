from __future__ import annotations

import re
from collections.abc import Iterable

from .entity_extractor import document_mentions_query
from .schemas import Category, Direction, EvidenceClaim, Horizon, SourceDocument


BULLISH_TERMS = {
    "beat": 0.35,
    "beats": 0.35,
    "raised guidance": 0.70,
    "raise guidance": 0.70,
    "upgrade": 0.45,
    "upgraded": 0.45,
    "strong demand": 0.45,
    "accelerating": 0.35,
    "record revenue": 0.55,
    "margin expansion": 0.45,
    "contract win": 0.55,
    "new contract": 0.45,
    "buyback": 0.35,
    "bullish": 0.25,
    "rally": 0.25,
    "surge": 0.25,
}

BEARISH_TERMS = {
    "miss": 0.35,
    "missed": 0.35,
    "cut guidance": 0.75,
    "lowered guidance": 0.75,
    "downgrade": 0.45,
    "downgraded": 0.45,
    "weak demand": 0.45,
    "slowing": 0.35,
    "margin pressure": 0.45,
    "valuation concerns": 0.45,
    "multiple compression": 0.45,
    "competition": 0.35,
    "investigation": 0.65,
    "lawsuit": 0.45,
    "false": 0.55,
    "not real": 0.55,
    "no contract": 0.50,
    "unconfirmed": 0.40,
    "denied": 0.45,
    "bearish": 0.25,
    "selloff": 0.25,
    "tumbled": 0.30,
    "fell": 0.20,
    "declined": 0.20,
}

CATEGORY_TERMS: list[tuple[Category, list[str]]] = [
    ("company_fundamental", ["revenue", "earnings", "guidance", "margin", "contract", "customer", "profit", "cash flow"]),
    ("sector_pressure", ["software", "ai", "semiconductor", "cloud", "defense tech", "sector", "peers"]),
    ("macro_pressure", ["fed", "interest rate", "treasury yield", "inflation", "jobs report", "cpi", "pce", "recession", "dollar"]),
    ("political_risk", ["tariff", "sanction", "war", "election", "congress", "white house", "geopolitical", "budget"]),
    ("valuation", ["valuation", "multiple", "price-to-sales", "p/e", "expensive", "frothy"]),
    ("liquidity_flow", ["fund flows", "rotation", "risk-off", "risk on", "liquidity", "ETF flows"]),
    ("technical_price_action", ["support", "resistance", "breakout", "breakdown", "moving average", "52-week"]),
]


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]


def classify_category(sentence: str) -> Category:
    sentence_lower = sentence.lower()
    for category, terms in CATEGORY_TERMS:
        if any(term in sentence_lower for term in terms):
            return category
    return "unknown"


def classify_horizon(sentence: str) -> Horizon:
    sentence_lower = sentence.lower()
    if any(x in sentence_lower for x in ["today", "intraday", "this morning", "afternoon"]):
        return "intraday"
    if any(x in sentence_lower for x in ["this week", "next week", "days"]):
        return "days"
    if any(x in sentence_lower for x in ["coming weeks", "weeks", "near term", "short term"]):
        return "days_to_weeks"
    if any(x in sentence_lower for x in ["quarter", "fiscal year", "full-year", "2026", "2027"]):
        return "quarters"
    return "unknown"


def score_direction(sentence: str) -> tuple[Direction, float]:
    sentence_lower = sentence.lower()
    bullish = sum(weight for term, weight in BULLISH_TERMS.items() if term in sentence_lower)
    bearish = sum(weight for term, weight in BEARISH_TERMS.items() if term in sentence_lower)

    if bullish == 0 and bearish == 0:
        return "neutral", 0.10
    if bullish > bearish:
        return "bullish", min(1.0, 0.20 + bullish - 0.50 * bearish)
    if bearish > bullish:
        return "bearish", min(1.0, 0.20 + bearish - 0.50 * bullish)
    return "neutral", min(0.35, bullish)


def estimate_novelty(sentence: str) -> float:
    sentence_lower = sentence.lower()
    novelty_terms = ["new", "unexpected", "surprise", "first", "breaking", "reported", "announced", "cut", "raised"]
    if any(term in sentence_lower for term in novelty_terms):
        return 0.75
    if any(term in sentence_lower for term in ["again", "continued", "ongoing", "still", "remains"]):
        return 0.30
    return 0.50


def extract_claims(query: str, docs: Iterable[SourceDocument]) -> list[EvidenceClaim]:
    claims: list[EvidenceClaim] = []
    query_upper = query.upper()

    for doc in docs:
        combined = f"{doc.title}. {doc.text}"
        if not document_mentions_query(combined, query):
            if query_upper not in {"SPY", "QQQ", "MARKET", "NASDAQ", "S&P", "SPX"}:
                continue

        for sentence in split_sentences(combined):
            direction, magnitude = score_direction(sentence)
            category = classify_category(sentence)
            if direction == "neutral" and category == "unknown":
                continue

            claims.append(
                EvidenceClaim(
                    entity=query_upper,
                    claim=sentence[:500],
                    category=category,
                    direction=direction,
                    magnitude=float(max(0.0, min(1.0, magnitude))),
                    reliability=float(max(0.0, min(1.0, doc.reliability))),
                    novelty=estimate_novelty(sentence),
                    time_horizon=classify_horizon(sentence),
                    source=doc.source,
                    source_title=doc.title,
                    source_url=doc.url,
                    published_at=doc.published_at,
                )
            )

    return claims
