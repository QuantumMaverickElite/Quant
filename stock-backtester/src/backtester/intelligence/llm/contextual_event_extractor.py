from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

from ..events.event_schemas import EventDirection, EventHorizon, EventScope, MarketEvent
from .semantic_event_classifier import HeuristicEventClassifier
from ..schemas import SourceDocument


EVENT_TERMS = {
    "price_action": [
        "stock falls",
        "stock fell",
        "shares fall",
        "shares fell",
        "shares dropped",
        "shares hit",
        "52-week low",
        "52 week low",
        "key price level",
        "losing streak",
        "underperforming",
        "buy point",
    ],
    "rates": ["fed", "fomc", "rate", "rates", "treasury yield", "yields", "bond yield"],
    "inflation": ["inflation", "cpi", "pce", "prices", "disinflation"],
    "earnings": ["earnings", "eps", "quarter", "revenue", "profit", "margin"],
    "guidance": ["guidance", "forecast", "outlook", "raised outlook", "cut outlook"],
    "valuation": ["valuation", "multiple", "price-to-sales", "p/e", "expensive", "frothy"],
    "liquidity": ["liquidity", "fund flows", "rotation", "risk-off", "risk on", "credit spread"],
    "legal": ["lawsuit", "probe", "investigation", "doj", "ftc", "sec charged"],
    "geopolitical": ["war", "sanction", "tariff", "election", "geopolitical", "white house", "congress", "iran", "china"],
    "sector_rotation": ["sector", "industry", "peers", "rotation", "basket"],
    "commodity": ["oil", "crude", "natural gas", "gold", "copper"],
    "company_fundamental": ["contract", "customer", "demand", "order", "backlog", "cash flow"],
}

BULLISH_TERMS = [
    "beat",
    "beats",
    "raised",
    "upgrade",
    "upgraded",
    "strong",
    "accelerating",
    "record",
    "expansion",
    "win",
    "surge",
    "rally",
    "bullish",
]

BEARISH_TERMS = [
    "miss",
    "missed",
    "cut",
    "lowered",
    "downgrade",
    "downgraded",
    "weak",
    "slowing",
    "pressure",
    "compression",
    "investigation",
    "lawsuit",
    "selloff",
    "tumbled",
    "fell",
    "bearish",
]

SCOPE_TERMS: list[tuple[EventScope, list[str]]] = [
    ("macro", ["fed", "fomc", "rate", "rates", "treasury", "inflation", "cpi", "pce", "recession", "dollar"]),
    ("political", ["tariff", "sanction", "war", "election", "congress", "white house", "geopolitical"]),
    ("commodity", ["oil", "crude", "natural gas", "gold", "copper"]),
    ("sector", ["sector", "industry", "semiconductor", "software", "banks", "utilities", "energy", "retail"]),
    ("index", ["nasdaq", "s&p", "spx", "qqq", "spy", "russell", "dow"]),
    ("peer_group", ["peers", "competitors", "basket"]),
]

PRICE_ACTION_TERMS = {
    "stock",
    "stocks",
    "share",
    "shares",
    "price",
    "trading",
    "rally",
    "rallied",
    "falls",
    "fell",
    "low",
    "high",
    "buy point",
    "underperforming",
}

POLITICAL_CONTEXT_TERMS = {
    "tariff",
    "sanction",
    "war",
    "election",
    "congress",
    "white house",
    "geopolitical",
    "iran",
    "china",
}

ENTITY_ALIASES = {
    "PLTR": ["palantir", "palantir technologies"],
    "QQQ": ["nasdaq", "nasdaq 100", "nasdaq-100"],
    "SPY": ["s&p 500", "s&p500", "spx"],
}

INDEX_QUERIES = {"QQQ", "SPY", "DIA", "IWM", "SPX", "NDX"}


def grounded_entity_scope(query: str) -> str:
    return "index" if query.upper() in INDEX_QUERIES else "ticker"


def term_matches(text: str, term: str) -> bool:
    """Match whole words for short terms and literal phrases for multi-word terms."""
    term = term.lower().strip()
    if not term:
        return False
    if " " in term or "-" in term:
        return term in text
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def any_term_matches(text: str, terms) -> bool:
    return any(term_matches(text, term) for term in terms)


@dataclass(slots=True)
class SentimentResult:
    direction: EventDirection
    confidence: float
    model: str


class SentimentBackend:
    def score(self, text: str) -> SentimentResult:
        low = text.lower()
        bullish = sum(1 for term in BULLISH_TERMS if term in low)
        bearish = sum(1 for term in BEARISH_TERMS if term in low)
        total = bullish + bearish
        if total == 0:
            return SentimentResult("neutral", 0.35, "heuristic")
        if bullish > bearish:
            return SentimentResult("bullish", min(0.90, 0.45 + 0.10 * (bullish - bearish)), "heuristic")
        if bearish > bullish:
            return SentimentResult("bearish", min(0.90, 0.45 + 0.10 * (bearish - bullish)), "heuristic")
        return SentimentResult("mixed", 0.45, "heuristic")

    def score_many(self, texts: list[str]) -> list[SentimentResult]:
        return [self.score(text) for text in texts]


class FinBertSentimentBackend(SentimentBackend):
    def __init__(
        self,
        *,
        model_name: str | None = None,
        batch_size: int | None = None,
        device: int | None = None,
    ) -> None:
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError("transformers is required for FinBERT sentiment") from exc

        if device is None:
            device = self._detect_device()
        self.model_name = model_name or os.environ.get("INTELLIGENCE_FINBERT_MODEL", "ProsusAI/finbert")
        self.batch_size = batch_size or int(os.environ.get("INTELLIGENCE_FINBERT_BATCH_SIZE", "16"))
        self.pipe = pipeline("text-classification", model=self.model_name, top_k=None, device=device)
        self._cache: dict[str, SentimentResult] = {}

    @staticmethod
    def _detect_device() -> int:
        requested = os.environ.get("INTELLIGENCE_NLP_DEVICE", "auto").lower()
        if requested == "cpu":
            return -1
        if requested.startswith("cuda"):
            return 0
        if requested == "auto":
            try:
                import torch

                return 0 if torch.cuda.is_available() else -1
            except ImportError:
                return -1
        return -1

    def score(self, text: str) -> SentimentResult:
        return self.score_many([text])[0]

    def score_many(self, texts: list[str]) -> list[SentimentResult]:
        normalized = [text[:2000] for text in texts]
        out: list[SentimentResult | None] = [None] * len(normalized)
        pending_texts: list[str] = []
        pending_indices: list[int] = []

        for idx, text in enumerate(normalized):
            cached = self._cache.get(text)
            if cached is not None:
                out[idx] = cached
            else:
                pending_texts.append(text)
                pending_indices.append(idx)

        if pending_texts:
            results = self.pipe(pending_texts, batch_size=self.batch_size, truncation=True)
            for idx, text, result in zip(pending_indices, pending_texts, results):
                sentiment = self._parse_result(result)
                self._cache[text] = sentiment
                out[idx] = sentiment

        return [item if item is not None else SentimentResult("neutral", 0.0, "finbert") for item in out]

    @staticmethod
    def _parse_result(result) -> SentimentResult:
        rows = result if result and isinstance(result, list) else [result]
        scores = {str(row["label"]).lower(): float(row["score"]) for row in rows}
        positive = scores.get("positive", scores.get("bullish", 0.0))
        negative = scores.get("negative", scores.get("bearish", 0.0))
        neutral = scores.get("neutral", 0.0)
        if max(positive, negative, neutral) == neutral:
            return SentimentResult("neutral", neutral, "finbert")
        if positive > negative:
            return SentimentResult("bullish", positive, "finbert")
        return SentimentResult("bearish", negative, "finbert")


def make_sentiment_backend(name: str) -> SentimentBackend:
    if name == "finbert":
        return FinBertSentimentBackend()
    if name == "auto":
        try:
            return FinBertSentimentBackend()
        except RuntimeError:
            return SentimentBackend()
    return SentimentBackend()


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if len(sentence.strip()) > 20]


def classification_context(
    *,
    title: str,
    sentences: list[str],
    idx: int,
    max_chars: int = 1200,
) -> str:
    """Build compact document context for semantic classification."""
    parts: list[str] = []
    if title.strip():
        parts.append(f"Title: {title.strip()}")
    if idx > 0:
        parts.append(f"Previous: {sentences[idx - 1]}")
    parts.append(f"Current: {sentences[idx]}")
    if idx + 1 < len(sentences):
        parts.append(f"Next: {sentences[idx + 1]}")
    text = " ".join(parts)
    return text[:max_chars]


def sentiment_context(*, title: str, sentence: str, max_chars: int = 700) -> str:
    """Keep sentiment focused on the current claim to avoid neighbor leakage."""
    if title.strip():
        return f"Title: {title.strip()} Current: {sentence}"[:max_chars]
    return sentence[:max_chars]


def event_type(text: str) -> str:
    low = text.lower()
    if any_term_matches(low, EVENT_TERMS["price_action"]):
        return "price_action"
    best = "general_news"
    best_count = 0
    for candidate, terms in EVENT_TERMS.items():
        count = sum(1 for term in terms if term_matches(low, term))
        if count > best_count:
            best = candidate
            best_count = count
    return best


def event_scope(text: str, query: str) -> EventScope:
    low = text.lower()
    aliases = ENTITY_ALIASES.get(query.upper(), [])
    query_mentioned = query.lower() in low or any_term_matches(low, aliases)
    has_price_action = any_term_matches(low, PRICE_ACTION_TERMS)
    has_political_context = any_term_matches(low, POLITICAL_CONTEXT_TERMS)

    if query_mentioned and has_price_action and not has_political_context:
        return grounded_entity_scope(query)

    if query_mentioned and not any(term_matches(low, term) for _, terms in SCOPE_TERMS for term in terms):
        return grounded_entity_scope(query)

    for scope, terms in SCOPE_TERMS:
        if any_term_matches(low, terms):
            if scope == "political" and query_mentioned and has_price_action:
                return grounded_entity_scope(query)
            return scope
    if query.lower() in low:
        return grounded_entity_scope(query)
    return "unknown"


def horizon(text: str) -> EventHorizon:
    low = text.lower()
    if any_term_matches(low, ["today", "intraday", "this morning", "afternoon"]):
        return "intraday"
    if any_term_matches(low, ["this week", "next week", "near term", "short term"]):
        return "days"
    if any_term_matches(low, ["weeks", "coming weeks", "month", "months"]):
        return "weeks"
    if any_term_matches(low, ["quarter", "year", "2026", "2027", "full-year"]):
        return "quarters"
    return "unknown"


def magnitude(text: str, sentiment_confidence: float, scope: EventScope) -> float:
    low = text.lower()
    intensity = 0.25
    strong_terms = ["surprise", "unexpected", "plunge", "surge", "crash", "record", "cut guidance", "raised guidance"]
    medium_terms = ["pressure", "weighs", "boost", "warns", "concerns", "slowing", "accelerating"]
    if any_term_matches(low, strong_terms):
        intensity += 0.35
    if any_term_matches(low, medium_terms):
        intensity += 0.20
    if scope in {"macro", "political", "sector", "index"}:
        intensity += 0.10
    intensity += 0.20 * sentiment_confidence
    return max(0.0, min(1.0, intensity))


def affected_entities(text: str, query: str) -> list[str]:
    entities = {query.upper()}
    known = ["SPY", "QQQ", "DIA", "IWM", "NASDAQ", "S&P 500", "FED", "FOMC", "OIL", "AI"]
    low = text.lower()
    for item in known:
        if item.lower() in low:
            entities.add(item)
    tickers = re.findall(r"\b[A-Z]{2,5}\b", text)
    entities.update(tickers[:10])
    return sorted(entities)


def query_mentioned_in_text(text: str, query: str) -> bool:
    low = text.lower()
    aliases = ENTITY_ALIASES.get(query.upper(), [])
    return query.lower() in low or any_term_matches(low, aliases)


def grounded_scope(
    sentence: str,
    context: str,
    query: str,
    classified_scope: str,
    scope_confidence: float,
    event_type_value: str,
) -> str:
    """Use entity aliases as guardrails around semantic scope classification."""
    low = sentence.lower()
    context_low = context.lower()
    mentioned = query_mentioned_in_text(sentence, query)
    context_mentions_query = query_mentioned_in_text(context, query)
    company_event_types = {
        "price_action",
        "earnings",
        "guidance",
        "company_fundamental",
        "analyst_rating",
        "m_and_a",
        "valuation",
    }
    macro_event_types = {"rates", "inflation", "liquidity", "commodity", "geopolitical"}

    if not mentioned and event_type_value in macro_event_types:
        return classified_scope

    if query.upper() != "MARKET" and mentioned:
        if classified_scope in {"unknown", "commodity"} or scope_confidence < 0.62:
            return grounded_entity_scope(query)
        if classified_scope in {"sector", "peer_group", "macro", "political", "index"}:
            if any_term_matches(low, PRICE_ACTION_TERMS) or any_term_matches(
                low,
                ["revenue", "earnings", "guidance", "contract", "demand", "customer", "margin", "shares", "stock"],
            ):
                return grounded_entity_scope(query)
        return classified_scope

    if query.upper() != "MARKET" and context_mentions_query and event_type_value in company_event_types:
        if any_term_matches(context_low, ["revenue", "earnings", "guidance", "contract", "demand", "customer", "margin", "shares", "stock"]):
            return grounded_entity_scope(query)

    if query.upper() == "MARKET":
        for ticker, aliases in ENTITY_ALIASES.items():
            if ticker.lower() in low or any_term_matches(low, aliases):
                if event_type_value in company_event_types:
                    return grounded_entity_scope(ticker)
                if any_term_matches(low, PRICE_ACTION_TERMS) or any_term_matches(
                    low,
                    ["revenue", "earnings", "guidance", "contract", "demand", "customer", "margin", "shares", "stock"],
                ):
                    return grounded_entity_scope(ticker)

            if event_type_value in company_event_types and (ticker.lower() in context_low or any_term_matches(context_low, aliases)):
                return grounded_entity_scope(ticker)

    return classified_scope


def grounded_event_type(sentence: str, context: str, classified_event_type: str) -> str:
    """Guard semantic taxonomy with finance-specific claim patterns."""
    low = sentence.lower()
    context_low = context.lower()

    financial_metric_terms = [
        "revenue",
        "sales",
        "eps",
        "earnings",
        "profit",
        "margin",
        "rule of 40",
        "commercial",
        "year over year",
        "y/y",
        "growth",
        "cash flow",
    ]
    forward_terms = ["guidance", "forecast", "outlook", "expects", "expected", "target", "projection"]
    valuation_terms = ["trillion", "market cap", "valuation", "multiple", "price target", "requires roughly"]
    deal_terms = ["merger", "acquisition", "acquire", "takeover", "buyout", "deal", "divestiture", "spin-off"]

    if any_term_matches(low, EVENT_TERMS["price_action"]):
        return "price_action"

    if any_term_matches(low, deal_terms):
        return "m_and_a"

    if classified_event_type == "m_and_a" and not any_term_matches(context_low, deal_terms):
        if any_term_matches(context_low, valuation_terms):
            return "valuation"
        return "general_news"

    if any_term_matches(low, financial_metric_terms):
        if any_term_matches(low, forward_terms):
            return "guidance"
        if any_term_matches(low, ["revenue", "eps", "earnings", "profit", "margin", "rule of 40", "year over year", "commercial"]):
            return "earnings"
        return "company_fundamental"

    if any_term_matches(low, valuation_terms) or (
        classified_event_type in {"valuation", "m_and_a"} and any_term_matches(context_low, valuation_terms)
    ):
        return "valuation"

    return classified_event_type


def event_id(query: str, source: str, text: str) -> str:
    raw = f"{query}|{source}|{text}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:16]


def extract_contextual_events(
    query: str,
    docs: list[SourceDocument],
    *,
    sentiment_backend: SentimentBackend | None = None,
    event_classifier=None,
) -> list[MarketEvent]:
    sentiment_backend = sentiment_backend or SentimentBackend()
    event_classifier = event_classifier or HeuristicEventClassifier()
    events: list[MarketEvent] = []
    for doc in docs:
        combined = f"{doc.title}. {doc.text}".strip()
        sentences = split_sentences(combined)
        candidates: list[tuple[str, str, EventScope]] = []
        for idx, sentence in enumerate(sentences):
            scope = event_scope(sentence, query)
            context = classification_context(title=doc.title, sentences=sentences, idx=idx)
            if (
                query.upper() not in {"MARKET", "MACRO", "QQQ", "SPY"}
                and not query_mentioned_in_text(context, query)
                and scope == "unknown"
            ):
                continue
            candidates.append((sentence, context, scope))

        contexts = [context for _, context, _ in candidates]
        sentiment_contexts = [sentiment_context(title=doc.title, sentence=sentence) for sentence, _, _ in candidates]
        sentiments = sentiment_backend.score_many(sentiment_contexts)
        fallback_event_types = [event_type(sentence) for sentence, _, _ in candidates]
        fallback_scopes = [scope for _, _, scope in candidates]
        classifications = event_classifier.classify_many(
            contexts,
            fallback_event_types=fallback_event_types,
            fallback_scopes=fallback_scopes,
        )
        for (sentence, context, _), sentiment, classification in zip(candidates, sentiments, classifications):
            event_type_value = grounded_event_type(sentence, context, classification.event_type)
            scope = grounded_scope(
                sentence,
                context,
                query,
                classification.scope,
                classification.scope_confidence,
                event_type_value,
            )
            if query.upper() == "MARKET" and scope == "ticker":
                continue
            events.append(
                MarketEvent(
                    event_id=event_id(query, doc.source, sentence),
                    query=query.upper(),
                    event_type=event_type_value,
                    scope=scope,
                    direction=sentiment.direction,
                    magnitude=round(magnitude(context, sentiment.confidence, scope), 4),
                    confidence=round(sentiment.confidence, 4),
                    novelty=0.50,
                    persistence=horizon(context),
                    affected_entities=affected_entities(context, query),
                    source=doc.source,
                    source_title=doc.title,
                    source_url=doc.url,
                    published_at=doc.published_at,
                    text=sentence[:700],
                    source_reliability=doc.reliability,
                    sentiment_model=sentiment.model,
                    event_classifier=classification.classifier_model,
                    event_type_confidence=classification.event_type_confidence,
                    scope_confidence=classification.scope_confidence,
                    raw_semantic_event_type=classification.event_type,
                    raw_semantic_scope=classification.scope,
                    classification_context=context[:700],
                )
            )
    return events


def is_global_scope(scope: EventScope) -> bool:
    return scope in {"macro", "political", "commodity", "sector", "index", "peer_group"}


def doc_text(doc: SourceDocument) -> str:
    return f"{doc.title}. {doc.text}".strip()


def doc_mentions_query(doc: SourceDocument, query: str) -> bool:
    return query_mentioned_in_text(doc_text(doc), query)


def document_has_global_event(doc: SourceDocument) -> bool:
    for sentence in split_sentences(doc_text(doc)):
        if is_global_scope(event_scope(sentence, "MARKET")):
            return True
    return False


def dedupe_documents_for_query(docs: list[SourceDocument], query: str) -> list[SourceDocument]:
    seen: set[str] = set()
    out: list[SourceDocument] = []
    for doc in docs:
        text = doc_text(doc)
        if not text:
            continue
        key = hashlib.sha1(f"{query}|{doc.source}|{doc.url}|{text}".encode("utf-8", errors="ignore")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        out.append(doc)
    return out


def extract_contextual_events_fast(
    queries: list[str],
    docs: list[SourceDocument],
    *,
    sentiment_backend: SentimentBackend | None = None,
    event_classifier=None,
    include_global_market_events: bool = True,
) -> list[MarketEvent]:
    """Extract events with query-aware prefiltering.

    Broad macro/sector/index events are emitted once under MARKET instead of
    being duplicated for every ticker. Ticker-specific events are only extracted
    from documents that mention that ticker.
    """
    sentiment_backend = sentiment_backend or SentimentBackend()
    event_classifier = event_classifier or HeuristicEventClassifier()
    normalized_queries = [query.strip().upper() for query in queries if query.strip()]
    events: list[MarketEvent] = []

    if include_global_market_events:
        global_docs = [doc for doc in docs if document_has_global_event(doc)]
        events.extend(
            extract_contextual_events(
                "MARKET",
                dedupe_documents_for_query(global_docs, "MARKET"),
                sentiment_backend=sentiment_backend,
                event_classifier=event_classifier,
            )
        )

    for query in normalized_queries:
        if query == "MARKET":
            continue
        query_docs = [doc for doc in docs if doc_mentions_query(doc, query)]
        if not query_docs:
            continue
        events.extend(
            extract_contextual_events(
                query,
                dedupe_documents_for_query(query_docs, query),
                sentiment_backend=sentiment_backend,
                event_classifier=event_classifier,
            )
        )

    seen_event_ids: set[str] = set()
    deduped: list[MarketEvent] = []
    for event in events:
        if event.event_id in seen_event_ids:
            continue
        seen_event_ids.add(event.event_id)
        deduped.append(event)
    return deduped
