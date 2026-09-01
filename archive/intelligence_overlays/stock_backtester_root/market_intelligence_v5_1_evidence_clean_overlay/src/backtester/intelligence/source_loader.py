from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .schemas import SourceDocument


TRUSTED_SOURCE_WEIGHTS = {
    "reuters": 0.90,
    "ap": 0.85,
    "associated press": 0.85,
    "sec": 0.95,
    "company investor relations": 0.85,
    "federal reserve": 0.95,
    "treasury": 0.95,
    "bls": 0.95,
    "bea": 0.95,
    "fred": 0.90,
    "gdelt": 0.60,
    "finnhub": 0.65,
    "alpha vantage": 0.65,
    "cnbc": 0.70,
    "cnn": 0.65,
    "fox news": 0.60,
    "marketwatch": 0.65,
    "yahoo finance": 0.60,
    "seeking alpha": 0.55,
    "local": 0.45,
    "reddit": 0.25,
    "stocktwits": 0.25,
    "x": 0.20,
    "twitter": 0.20,
    "instagram": 0.20,
}


def source_reliability(source: str) -> float:
    source_lower = source.lower().strip()
    for key, weight in TRUSTED_SOURCE_WEIGHTS.items():
        if key in source_lower:
            return weight
    return 0.55


def load_jsonl(path: str | Path) -> list[SourceDocument]:
    docs: list[SourceDocument] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            source = row.get("source", "unknown")
            docs.append(
                SourceDocument(
                    source=source,
                    title=row.get("title", ""),
                    text=row.get("text", ""),
                    url=row.get("url"),
                    published_at=row.get("published_at"),
                    reliability=float(row.get("reliability", source_reliability(source))),
                )
            )
    return docs


def from_texts(rows: Iterable[dict]) -> list[SourceDocument]:
    docs: list[SourceDocument] = []
    for row in rows:
        source = row.get("source", "manual")
        docs.append(
            SourceDocument(
                source=source,
                title=row.get("title", ""),
                text=row.get("text", ""),
                url=row.get("url"),
                published_at=row.get("published_at"),
                reliability=float(row.get("reliability", source_reliability(source))),
            )
        )
    return docs
