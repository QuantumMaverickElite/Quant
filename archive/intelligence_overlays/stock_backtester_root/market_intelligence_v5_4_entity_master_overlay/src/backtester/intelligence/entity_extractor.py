from __future__ import annotations

from .entity_resolver import aliases_for_query, text_mentions_entity


COMMON_INDEX_ALIASES = {
    "SPY": ["SPY", "S&P 500", "S&P500", "SPX"],
    "QQQ": ["QQQ", "Nasdaq", "Nasdaq 100", "NDX"],
    "DIA": ["DIA", "Dow Jones", "DJIA"],
    "IWM": ["IWM", "Russell 2000"],
}


def normalize_query_entities(query: str) -> list[str]:
    out: list[str] = []
    for alias in aliases_for_query(query):
        out.append(alias)
        out.extend(COMMON_INDEX_ALIASES.get(alias.upper(), []))
    return sorted(set(out), key=len, reverse=True)


def document_mentions_query(text: str, query: str) -> bool:
    return text_mentions_entity(text, query)
