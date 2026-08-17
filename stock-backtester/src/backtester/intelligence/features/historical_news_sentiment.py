from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


SENTIMENT_TO_SCORE = {
    "bullish": 1.0,
    "positive": 1.0,
    "bearish": -1.0,
    "negative": -1.0,
    "neutral": 0.0,
    "mixed": 0.0,
}


@dataclass(slots=True)
class SimpleSentimentResult:
    direction: str
    confidence: float
    model: str


class HistoricalHeuristicSentimentBackend:
    bullish_terms = (
        "beat",
        "beats",
        "raised",
        "upgrade",
        "upgraded",
        "strong",
        "surge",
        "rally",
        "growth",
        "outperform",
        "bullish",
    )
    bearish_terms = (
        "miss",
        "missed",
        "cut",
        "lowered",
        "downgrade",
        "downgraded",
        "weak",
        "falls",
        "fell",
        "pressure",
        "lawsuit",
        "bearish",
    )

    def score_many(self, texts: list[str]) -> list[SimpleSentimentResult]:
        return [self.score(text) for text in texts]

    def score(self, text: str) -> SimpleSentimentResult:
        low = text.lower()
        bullish = sum(1 for term in self.bullish_terms if term in low)
        bearish = sum(1 for term in self.bearish_terms if term in low)
        if bullish > bearish:
            return SimpleSentimentResult("bullish", min(0.9, 0.45 + 0.1 * (bullish - bearish)), "heuristic")
        if bearish > bullish:
            return SimpleSentimentResult("bearish", min(0.9, 0.45 + 0.1 * (bearish - bullish)), "heuristic")
        return SimpleSentimentResult("neutral", 0.35, "heuristic")


def make_historical_sentiment_backend(name: str):
    if name == "heuristic":
        return HistoricalHeuristicSentimentBackend()
    try:
        from ..llm.contextual_event_extractor import make_sentiment_backend

        return make_sentiment_backend(name)
    except Exception:
        if name == "auto":
            return HistoricalHeuristicSentimentBackend()
        raise


def read_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl_rows(rows: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def text_for_sentiment(record: dict, max_chars: int = 1200) -> str:
    title = str(record.get("title") or "").strip()
    text = str(record.get("text") or "").strip()
    if title and text and not text.startswith(title):
        combined = f"Title: {title}. Text: {text}"
    else:
        combined = text or title
    return combined[:max_chars]


def sentiment_numeric_score(direction: str, confidence: float) -> float:
    return SENTIMENT_TO_SCORE.get(direction.lower(), 0.0) * float(confidence)


def should_score_record(record: dict, *, include_analyst: bool = False) -> bool:
    if include_analyst:
        return True
    return str(record.get("source_kind") or "") != "analyst_recommendation"


def enrich_historical_news_sentiment(
    *,
    input_jsonl: str | Path,
    output_jsonl: str | Path,
    backend: str = "finbert",
    batch_size: int = 64,
    limit: int | None = None,
    include_analyst: bool = False,
    checkpoint_every: int = 0,
    nlp_device: str | None = None,
) -> list[dict]:
    if nlp_device:
        os.environ["INTELLIGENCE_NLP_DEVICE"] = nlp_device
    rows = read_jsonl(input_jsonl)
    if limit is not None:
        rows = rows[: int(limit)]

    scorer = make_historical_sentiment_backend(backend)
    texts: list[str] = []
    row_indices: list[int] = []
    for idx, row in enumerate(rows):
        raw = row.get("raw")
        if not isinstance(raw, dict):
            raw = {}
            row["raw"] = raw
        if raw.get("model_sentiment_score") is not None:
            continue
        if not should_score_record(row, include_analyst=include_analyst):
            continue
        text = text_for_sentiment(row)
        if not text:
            continue
        texts.append(text)
        row_indices.append(idx)

    for start in range(0, len(texts), batch_size):
        chunk = texts[start : start + batch_size]
        chunk_indices = row_indices[start : start + batch_size]
        results = scorer.score_many(chunk)
        for idx, result in zip(chunk_indices, results):
            raw = rows[idx].setdefault("raw", {})
            raw["model_sentiment_direction"] = result.direction
            raw["model_sentiment_confidence"] = float(result.confidence)
            raw["model_sentiment_score"] = sentiment_numeric_score(result.direction, result.confidence)
            raw["model_sentiment_backend"] = result.model
        if checkpoint_every > 0 and (start + len(chunk)) % checkpoint_every < batch_size:
            write_jsonl_rows(rows, output_jsonl)

    write_jsonl_rows(rows, output_jsonl)
    return rows
