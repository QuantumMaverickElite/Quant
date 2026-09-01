from __future__ import annotations

import re
from dataclasses import asdict, dataclass


Usage = str


@dataclass(frozen=True, slots=True)
class ProviderPolicy:
    provider: str
    quality_tier: str
    min_relevance_score: float
    min_request_interval_seconds: float
    allowed_for_live_scoring: bool = True
    allowed_for_backtesting: bool = True
    allowed_for_ml_training: bool = True
    allowed_for_storage: bool = True
    requires_confirmation: bool = False
    is_official_source: bool = False
    notes: str = ""

    def allows(self, usage: Usage) -> bool:
        usage = usage.lower().strip()
        if usage in {"live", "live_scoring"}:
            return self.allowed_for_live_scoring
        if usage in {"backtest", "backtesting"}:
            return self.allowed_for_backtesting
        if usage in {"ml", "training", "ml_training"}:
            return self.allowed_for_ml_training
        if usage == "storage":
            return self.allowed_for_storage
        raise ValueError(f"Unknown source usage: {usage}")

    def to_dict(self) -> dict:
        return asdict(self)


QUERY_ALIASES: dict[str, tuple[str, ...]] = {
    "PLTR": ("PLTR", "$PLTR", "Palantir", "Palantir Technologies"),
    "MSFT": ("MSFT", "$MSFT", "Microsoft", "Microsoft Corp", "Microsoft Corporation"),
    "NVDA": ("NVDA", "$NVDA", "Nvidia", "NVIDIA Corporation"),
    "META": ("META", "$META", "Meta Platforms", "Facebook"),
    "TSLA": ("TSLA", "$TSLA", "Tesla", "Tesla Inc"),
    "AVGO": ("AVGO", "$AVGO", "Broadcom"),
    "ORCL": ("ORCL", "$ORCL", "Oracle"),
    "QQQ": ("QQQ", "$QQQ", "Nasdaq 100", "Nasdaq-100", "Invesco QQQ"),
    "SPY": ("SPY", "$SPY", "S&P 500", "SPDR S&P 500 ETF", "SPX"),
    "MARKET": ("stock market", "equity market", "Wall Street", "Nasdaq", "S&P 500", "SPX"),
    "MACRO": ("Federal Reserve", "Fed", "Treasury yield", "inflation", "CPI", "PCE", "jobs report"),
}


PROVIDER_ALIASES = {
    "alpha_vantage": "alpha_vantage_news_sentiment",
    "finnhub_news": "finnhub_company_news",
    "finnhub_recommendations": "finnhub_recommendation_trends",
    "massive_news": "massive_ticker_news",
    "polygon_news": "polygon_ticker_news",
    "newsapi": "newsapi_everything",
    "gdelt": "gdelt_doc",
    "gdelt_historical": "gdelt_doc",
    "sec": "sec_edgar_submissions",
    "sec_edgar": "sec_edgar_submissions",
    "edgar": "sec_edgar_submissions",
    "company_ir": "company_investor_relations",
    "investor_relations": "company_investor_relations",
    "reddit": "reddit",
}


PROVIDER_POLICIES: dict[str, ProviderPolicy] = {
    "alpha_vantage_news_sentiment": ProviderPolicy(
        provider="alpha_vantage_news_sentiment",
        quality_tier="medium",
        min_relevance_score=0.30,
        min_request_interval_seconds=12.0,
        notes="Useful sentiment feed; rate limits are tight on free keys.",
    ),
    "finnhub_company_news": ProviderPolicy(
        provider="finnhub_company_news",
        quality_tier="medium_high",
        min_relevance_score=0.35,
        min_request_interval_seconds=1.2,
        notes="Ticker-scoped company news; back off on 429s.",
    ),
    "finnhub_recommendation_trends": ProviderPolicy(
        provider="finnhub_recommendation_trends",
        quality_tier="high",
        min_relevance_score=1.00,
        min_request_interval_seconds=1.2,
        notes="Structured analyst trend data, not article text.",
    ),
    "sec_edgar_submissions": ProviderPolicy(
        provider="sec_edgar_submissions",
        quality_tier="official",
        min_relevance_score=1.00,
        min_request_interval_seconds=0.25,
        requires_confirmation=False,
        is_official_source=True,
        notes="Official SEC EDGAR filings. Allowed for training and confirmation.",
    ),
    "company_investor_relations": ProviderPolicy(
        provider="company_investor_relations",
        quality_tier="official",
        min_relevance_score=0.80,
        min_request_interval_seconds=1.0,
        requires_confirmation=False,
        is_official_source=True,
        notes="Company-controlled official investor-relations or press-release source.",
    ),
    "massive_ticker_news": ProviderPolicy(
        provider="massive_ticker_news",
        quality_tier="high",
        min_relevance_score=0.40,
        min_request_interval_seconds=15.0,
        notes="High-value ticker news. Use conservative sleep on free tier.",
    ),
    "polygon_ticker_news": ProviderPolicy(
        provider="polygon_ticker_news",
        quality_tier="high",
        min_relevance_score=0.40,
        min_request_interval_seconds=15.0,
        notes="Legacy Polygon ticker news path; treat like Massive.",
    ),
    "newsapi_everything": ProviderPolicy(
        provider="newsapi_everything",
        quality_tier="medium",
        min_relevance_score=0.50,
        min_request_interval_seconds=2.0,
        allowed_for_ml_training=False,
        notes="Free/developer plans are not suitable as a default training source.",
    ),
    "gdelt_doc": ProviderPolicy(
        provider="gdelt_doc",
        quality_tier="low",
        min_relevance_score=0.75,
        min_request_interval_seconds=1.0,
        allowed_for_ml_training=False,
        requires_confirmation=True,
        notes="Discovery-only by default. Too noisy for direct ML training.",
    ),
    "reddit": ProviderPolicy(
        provider="reddit",
        quality_tier="low",
        min_relevance_score=0.90,
        min_request_interval_seconds=2.0,
        allowed_for_backtesting=False,
        allowed_for_ml_training=False,
        requires_confirmation=True,
        notes="Disabled for training/backtests because of policy and rumor risk.",
    ),
}

DEFAULT_POLICY = ProviderPolicy(
    provider="unknown",
    quality_tier="unknown",
    min_relevance_score=0.50,
    min_request_interval_seconds=2.0,
    allowed_for_ml_training=False,
    requires_confirmation=True,
    notes="Unknown provider; exclude from ML training unless explicitly reviewed.",
)


def canonical_provider(provider: object) -> str:
    value = str(provider or "").strip().lower()
    value = value.replace("-", "_").replace(" ", "_")
    return PROVIDER_ALIASES.get(value, value)


def provider_policy(provider: object) -> ProviderPolicy:
    return PROVIDER_POLICIES.get(canonical_provider(provider), DEFAULT_POLICY)


def provider_allowed_for_usage(provider: object, usage: Usage) -> bool:
    return provider_policy(provider).allows(usage)


def provider_min_interval(provider: object) -> float:
    return float(provider_policy(provider).min_request_interval_seconds)


def normalized_query_aliases(query: str) -> list[str]:
    query_upper = query.strip().upper()
    aliases = list(QUERY_ALIASES.get(query_upper, (query_upper,)))
    if len(query_upper) <= 5:
        aliases.append(f"${query_upper}")
    out: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        value = alias.strip()
        key = value.lower()
        if value and key not in seen:
            out.append(value)
            seen.add(key)
    return out


def query_relevance(query: str, text: str) -> tuple[list[str], float]:
    if query.upper() in {"MARKET", "MACRO"}:
        aliases = normalized_query_aliases(query)
    else:
        aliases = normalized_query_aliases(query)
    haystack = f" {text.lower()} "
    matched: list[str] = []
    score = 0.0
    for alias in aliases:
        alias_low = alias.lower()
        if alias_low.startswith("$"):
            if alias_low in haystack:
                matched.append(alias)
                score += 0.60
            continue
        pattern = r"(?<![a-z0-9])" + re.escape(alias_low) + r"(?![a-z0-9])"
        if re.search(pattern, haystack):
            matched.append(alias)
            if alias_low == query.lower():
                score += 0.45
            elif len(alias_low) <= 6:
                score += 0.35
            else:
                score += 0.70
    return sorted(set(matched), key=str.lower), min(1.0, score)


def annotate_record_policy(record: dict, *, usage: Usage | None = None) -> dict:
    row = dict(record)
    policy = provider_policy(row.get("provider"))
    row["provider_policy"] = {
        "quality_tier": policy.quality_tier,
        "min_relevance_score": policy.min_relevance_score,
        "requires_confirmation": policy.requires_confirmation,
        "allowed_for_live_scoring": policy.allowed_for_live_scoring,
        "allowed_for_backtesting": policy.allowed_for_backtesting,
        "allowed_for_ml_training": policy.allowed_for_ml_training,
        "allowed_for_storage": policy.allowed_for_storage,
        "is_official_source": policy.is_official_source,
        "notes": policy.notes,
    }
    if usage is not None:
        row["provider_policy"]["allowed_for_usage"] = policy.allows(usage)
        row["provider_policy"]["usage"] = usage
    return row


def record_allowed_for_usage(record: dict, usage: Usage) -> bool:
    return provider_allowed_for_usage(record.get("provider"), usage)


def record_passes_policy(record: dict, *, usage: Usage | None = None, min_relevance_score: float | None = None) -> bool:
    policy = provider_policy(record.get("provider"))
    if usage is not None and not policy.allows(usage):
        return False
    threshold = policy.min_relevance_score if min_relevance_score is None else max(policy.min_relevance_score, min_relevance_score)
    try:
        relevance = float(record.get("relevance_score") or 0.0)
    except (TypeError, ValueError):
        relevance = 0.0
    return relevance >= threshold
