from __future__ import annotations

import re


COMMON_INDEX_ALIASES = {
    "SPY": ["SPY", "S&P 500", "S&P500", "SPX"],
    "QQQ": ["QQQ", "Nasdaq", "Nasdaq 100", "NDX"],
    "DIA": ["DIA", "Dow Jones", "DJIA"],
    "IWM": ["IWM", "Russell 2000"],
}


def normalize_query_entities(query: str) -> list[str]:
    parts = [p.strip().upper() for p in re.split(r"[, ]+", query) if p.strip()]
    out: list[str] = []
    for part in parts:
        out.append(part)
        out.extend(COMMON_INDEX_ALIASES.get(part, []))
    return sorted(set(out), key=len, reverse=True)


def document_mentions_query(text: str, query: str) -> bool:
    haystack = text.lower()
    return any(entity.lower() in haystack for entity in normalize_query_entities(query))
