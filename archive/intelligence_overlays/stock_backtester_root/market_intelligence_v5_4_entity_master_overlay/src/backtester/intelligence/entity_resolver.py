from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


ENTITY_MASTER_ENV = "ENTITY_MASTER_PATH"
DEFAULT_ENTITY_MASTER_PATH = Path("data/intelligence/entity_master.csv")


STATIC_ENTITY_ALIASES: dict[str, tuple[str, ...]] = {
    "PLTR": ("PLTR", "$PLTR", "Palantir", "Palantir Technologies", "Palantir Technologies Inc"),
    "MSFT": ("MSFT", "$MSFT", "Microsoft", "Microsoft Corp", "Microsoft Corporation"),
    "NVDA": ("NVDA", "$NVDA", "Nvidia", "NVIDIA Corporation"),
    "META": ("META", "$META", "Meta Platforms", "Facebook"),
    "TSLA": ("TSLA", "$TSLA", "Tesla", "Tesla Inc"),
    "AVGO": ("AVGO", "$AVGO", "Broadcom", "Broadcom Inc"),
    "ORCL": ("ORCL", "$ORCL", "Oracle", "Oracle Corporation"),
    "QQQ": ("QQQ", "$QQQ", "Nasdaq 100", "Nasdaq-100", "Invesco QQQ"),
    "SPY": ("SPY", "$SPY", "S&P 500", "SPDR S&P 500 ETF", "SPX"),
    "DIA": ("DIA", "$DIA", "Dow Jones", "DJIA"),
    "IWM": ("IWM", "$IWM", "Russell 2000"),
    "MARKET": ("stock market", "equity market", "Wall Street", "Nasdaq", "S&P 500", "SPX"),
    "MACRO": ("Federal Reserve", "Fed", "Treasury yield", "inflation", "CPI", "PCE", "jobs report"),
}


LEGAL_SUFFIX_PATTERNS = (
    r"\bincorporated\b",
    r"\binc\b\.?",
    r"\bcorporation\b",
    r"\bcorp\b\.?",
    r"\bcompany\b",
    r"\bco\b\.?",
    r"\blimited\b",
    r"\bltd\b\.?",
    r"\bplc\b",
    r"\bclass\s+[a-z]\b",
    r"\bcommon\s+stock\b",
)


@dataclass(frozen=True, slots=True)
class EntityRecord:
    ticker: str
    cik: str = ""
    legal_name: str = ""
    common_name: str = ""
    aliases: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    exchange: str = ""
    sector: str = ""
    source: str = ""
    confidence: float = 1.0
    active: bool = True

    def all_aliases(self) -> tuple[str, ...]:
        values = [self.ticker, f"${self.ticker}", self.legal_name, self.common_name]
        values.extend(self.aliases)
        values.extend(self.domains)
        return unique_strings(values)


@dataclass(frozen=True, slots=True)
class EntityMatch:
    ticker: str
    matched_terms: tuple[str, ...]
    score: float
    confidence: float
    source: str = ""


def unique_strings(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        key = text.casefold()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return tuple(out)


def split_multi_value(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    text = str(value).strip()
    if not text:
        return ()
    parts = re.split(r"\s*[|;,]\s*", text)
    return unique_strings(tuple(part for part in parts if part))


def normalize_name(value: str) -> str:
    text = str(value or "").replace("&", " and ")
    text = re.sub(r"[^A-Za-z0-9$]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return text


def derive_common_name(legal_name: str) -> str:
    text = str(legal_name or "").strip()
    if not text:
        return ""
    value = text
    for pattern in LEGAL_SUFFIX_PATTERNS:
        value = re.sub(pattern, "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip(" ,.-")
    return value or text


def term_pattern(term: str) -> re.Pattern[str]:
    raw = str(term or "").strip().casefold()
    if raw.startswith("$"):
        return re.compile(r"(?<![A-Za-z0-9])" + re.escape(raw) + r"(?![A-Za-z0-9])", re.IGNORECASE)
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(raw) + r"(?![A-Za-z0-9])", re.IGNORECASE)


def term_score(term: str, query: str) -> float:
    clean = str(term or "").strip()
    low = clean.casefold()
    query_low = str(query or "").strip().casefold()
    if low.startswith("$"):
        return 0.60
    if low == query_low:
        return 0.45 if len(clean) <= 6 else 0.75
    if len(clean) <= 5 and clean.isupper():
        return 0.35
    if len(clean) <= 6:
        return 0.35
    return 0.70


def default_entity_master_path() -> Path:
    configured = os.environ.get(ENTITY_MASTER_ENV)
    return Path(configured) if configured else DEFAULT_ENTITY_MASTER_PATH


def record_from_row(row: dict[str, object]) -> EntityRecord | None:
    ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
    if not ticker:
        return None
    legal_name = str(row.get("legal_name") or row.get("title") or row.get("name") or "").strip()
    common_name = str(row.get("common_name") or "").strip() or derive_common_name(legal_name)
    aliases = split_multi_value(row.get("aliases"))
    domains = split_multi_value(row.get("domains") or row.get("domain"))
    try:
        confidence = float(row.get("confidence") or 1.0)
    except (TypeError, ValueError):
        confidence = 1.0
    active_raw = str(row.get("active") if row.get("active") is not None else "true").strip().casefold()
    return EntityRecord(
        ticker=ticker,
        cik=str(row.get("cik") or row.get("cik_str") or "").strip(),
        legal_name=legal_name,
        common_name=common_name,
        aliases=aliases,
        domains=domains,
        exchange=str(row.get("exchange") or "").strip(),
        sector=str(row.get("sector") or "").strip(),
        source=str(row.get("source") or "").strip(),
        confidence=confidence,
        active=active_raw not in {"0", "false", "no", "n"},
    )


def static_records() -> list[EntityRecord]:
    records: list[EntityRecord] = []
    for ticker, aliases in STATIC_ENTITY_ALIASES.items():
        legal_name = aliases[-1] if aliases else ticker
        records.append(
            EntityRecord(
                ticker=ticker.upper(),
                legal_name=legal_name,
                common_name=derive_common_name(legal_name),
                aliases=tuple(aliases),
                source="static",
                confidence=0.70,
            )
        )
    return records


class EntityResolver:
    def __init__(self, records: list[EntityRecord] | None = None) -> None:
        self.records = records or static_records()
        self.by_ticker: dict[str, EntityRecord] = {}
        self.by_alias: dict[str, EntityRecord] = {}
        for record in self.records:
            self.by_ticker[record.ticker.upper()] = record
            for alias in record.all_aliases():
                key = normalize_name(alias)
                if key:
                    self.by_alias.setdefault(key, record)

    @classmethod
    def from_csv(cls, path: str | Path | None = None, *, include_static: bool = True) -> "EntityResolver":
        records = static_records() if include_static else []
        source_path = Path(path) if path else default_entity_master_path()
        if source_path.exists():
            with source_path.open("r", encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    record = record_from_row(row)
                    if record is not None:
                        records.append(record)
        return cls(merge_records(records))

    def resolve_query(self, query: str) -> EntityRecord | None:
        raw = str(query or "").strip()
        if not raw:
            return None
        ticker = raw.upper().lstrip("$")
        if ticker in self.by_ticker:
            return self.by_ticker[ticker]
        return self.by_alias.get(normalize_name(raw))

    def aliases_for_query(self, query: str) -> list[str]:
        record = self.resolve_query(query)
        if record is None:
            out = [str(query or "").strip()]
            query_upper = out[0].upper() if out and out[0] else ""
            if query_upper and len(query_upper) <= 5:
                out.append(f"${query_upper}")
            return list(unique_strings(tuple(out)))
        return list(record.all_aliases())

    def query_relevance(self, query: str, text: str) -> tuple[list[str], float]:
        aliases = self.aliases_for_query(query)
        matched: list[str] = []
        score = 0.0
        body = str(text or "")
        for alias in sorted(aliases, key=len, reverse=True):
            if not alias:
                continue
            if term_pattern(alias).search(body):
                matched.append(alias)
                score += term_score(alias, query)
        return sorted(set(matched), key=str.lower), min(1.0, score)

    def resolve_text_to_entities(self, text: str, *, min_score: float = 0.35) -> list[EntityMatch]:
        matches: list[EntityMatch] = []
        for ticker, record in sorted(self.by_ticker.items()):
            matched, score = self.query_relevance(ticker, text)
            if score >= min_score:
                matches.append(
                    EntityMatch(
                        ticker=ticker,
                        matched_terms=tuple(matched),
                        score=score,
                        confidence=record.confidence,
                        source=record.source,
                    )
                )
        return sorted(matches, key=lambda item: (-item.score, item.ticker))


def merge_records(records: list[EntityRecord]) -> list[EntityRecord]:
    by_ticker: dict[str, EntityRecord] = {}
    for record in records:
        ticker = record.ticker.upper()
        existing = by_ticker.get(ticker)
        if existing is None:
            by_ticker[ticker] = record
            continue
        aliases = unique_strings(existing.all_aliases() + record.all_aliases())
        domains = unique_strings(existing.domains + record.domains)
        by_ticker[ticker] = EntityRecord(
            ticker=ticker,
            cik=record.cik or existing.cik,
            legal_name=record.legal_name or existing.legal_name,
            common_name=record.common_name or existing.common_name,
            aliases=aliases,
            domains=domains,
            exchange=record.exchange or existing.exchange,
            sector=record.sector or existing.sector,
            source=record.source or existing.source,
            confidence=max(existing.confidence, record.confidence),
            active=existing.active or record.active,
        )
    return list(by_ticker.values())


@lru_cache(maxsize=8)
def resolver_for_path(path_key: str) -> EntityResolver:
    path = Path(path_key) if path_key else default_entity_master_path()
    return EntityResolver.from_csv(path)


def default_resolver() -> EntityResolver:
    return resolver_for_path(str(default_entity_master_path()))


def aliases_for_query(query: str) -> list[str]:
    return default_resolver().aliases_for_query(query)


def query_relevance(query: str, text: str) -> tuple[list[str], float]:
    return default_resolver().query_relevance(query, text)


def text_mentions_entity(text: str, query: str, *, min_score: float = 0.35) -> bool:
    _, score = query_relevance(query, text)
    return score >= min_score
