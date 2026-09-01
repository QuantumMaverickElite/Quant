from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from .historical_source_collector import (
    HistoricalSourceRecord,
    dedupe_records,
    parse_ymd,
    stable_record_id,
    utc_now_iso,
    write_jsonl,
)


ALPHA_VANTAGE_NEWS_URL = "https://www.alphavantage.co/query"
FINNHUB_COMPANY_NEWS_URL = "https://finnhub.io/api/v1/company-news"
FINNHUB_RECOMMENDATION_URL = "https://finnhub.io/api/v1/stock/recommendation"
NEWSAPI_EVERYTHING_URL = "https://newsapi.org/v2/everything"
POLYGON_TICKER_NEWS_URL = "https://api.polygon.io/v2/reference/news"


@dataclass(frozen=True)
class ProviderRequest:
    provider: str
    query: str
    start: date
    end: date
    limit: int


def date_to_av(value: date) -> str:
    return value.strftime("%Y%m%dT%H%M")


def parse_epoch_seconds(value: object) -> str | None:
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def parse_polygon_time(value: object) -> str | None:
    if not value:
        return None
    return str(value)


def compact_hash(*parts: object) -> str:
    raw = "|".join(str(part or "") for part in parts).encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:16]


def domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url).netloc.replace("www.", "") or None
    except ValueError:
        return None


def normalized_query_match(query: str, text: str) -> tuple[list[str], float]:
    if query.upper() in {"MARKET", "MACRO"}:
        return [query.lower()], 1.0
    terms = {query.lower()}
    if len(query) <= 5:
        terms.add(f"${query.lower()}")
    haystack = text.lower()
    matched = sorted(term for term in terms if term and term in haystack)
    score = 1.0 if matched else 0.0
    return matched, score


class JsonApiClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        sleep_seconds: float = 0.25,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
        user_agent: str = "stock-backtester-market-intelligence/0.1",
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.sleep_seconds = sleep_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.user_agent = user_agent

    def open_json(self, url: str, *, headers: dict[str, str] | None = None) -> dict | list:
        request_headers = {"User-Agent": self.user_agent, **(headers or {})}
        request = urllib.request.Request(url, headers=request_headers)
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if self.sleep_seconds > 0:
                    time.sleep(self.sleep_seconds)
                return payload
            except HTTPError as exc:
                last_error = exc
                retryable = exc.code in {408, 425, 429, 500, 502, 503, 504}
                if not retryable or attempt >= self.max_retries:
                    break
                delay = self._retry_delay(exc, attempt)
                print(f"HTTP {exc.code}; retrying in {delay:.1f}s")
                time.sleep(delay)
            except (TimeoutError, URLError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                delay = self.backoff_seconds * (2**attempt)
                print(f"Request failed ({exc}); retrying in {delay:.1f}s")
                time.sleep(delay)
        print(f"Request skipped after retries: {last_error}")
        return {}

    def _retry_delay(self, exc: HTTPError, attempt: int) -> float:
        retry_after = exc.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        return self.backoff_seconds * (2**attempt)


def alpha_vantage_record(query: str, item: dict) -> HistoricalSourceRecord:
    title = str(item.get("title") or "").strip()
    summary = str(item.get("summary") or "").strip()
    url = item.get("url")
    source = str(item.get("source") or "Alpha Vantage")
    published_at = item.get("time_published")
    text = f"{title}. {summary}".strip()
    matched, relevance = normalized_query_match(query, f"{title} {summary} {url or ''}")
    raw_sentiment = item.get("overall_sentiment_score")
    try:
        relevance = max(float(relevance), min(1.0, abs(float(raw_sentiment)) + 0.25))
    except (TypeError, ValueError):
        pass
    return HistoricalSourceRecord(
        query=query.upper(),
        provider="alpha_vantage_news_sentiment",
        source=source,
        source_kind="news_sentiment",
        title=title,
        text=text,
        url=url,
        published_at=published_at,
        fetched_at=utc_now_iso(),
        domain=domain_from_url(url),
        language=None,
        source_country=None,
        provider_article_id=stable_record_id(query=query.upper(), url=url, title=title, published_at=published_at),
        matched_terms=matched,
        relevance_score=round(float(relevance), 4),
        raw=item,
    )


def finnhub_news_record(query: str, item: dict) -> HistoricalSourceRecord:
    title = str(item.get("headline") or "").strip()
    summary = str(item.get("summary") or "").strip()
    url = item.get("url")
    published_at = parse_epoch_seconds(item.get("datetime"))
    source = str(item.get("source") or "Finnhub")
    text = f"{title}. {summary}".strip()
    matched, relevance = normalized_query_match(query, f"{title} {summary} {url or ''}")
    return HistoricalSourceRecord(
        query=query.upper(),
        provider="finnhub_company_news",
        source=source,
        source_kind="news",
        title=title,
        text=text,
        url=url,
        published_at=published_at,
        fetched_at=utc_now_iso(),
        domain=domain_from_url(url),
        language=None,
        source_country=None,
        provider_article_id=str(item.get("id") or compact_hash(query, url, title, published_at)),
        matched_terms=matched,
        relevance_score=relevance,
        raw=item,
    )


def finnhub_recommendation_record(query: str, item: dict) -> HistoricalSourceRecord:
    period = str(item.get("period") or "")
    strong_buy = int(item.get("strongBuy") or 0)
    buy = int(item.get("buy") or 0)
    hold = int(item.get("hold") or 0)
    sell = int(item.get("sell") or 0)
    strong_sell = int(item.get("strongSell") or 0)
    title = f"{query.upper()} analyst recommendation trend for {period}"
    text = (
        f"{query.upper()} analyst recommendations for {period}: "
        f"strongBuy={strong_buy}, buy={buy}, hold={hold}, sell={sell}, strongSell={strong_sell}."
    )
    return HistoricalSourceRecord(
        query=query.upper(),
        provider="finnhub_recommendation_trends",
        source="Finnhub",
        source_kind="analyst_recommendation",
        title=title,
        text=text,
        url=None,
        published_at=period,
        fetched_at=utc_now_iso(),
        domain="finnhub.io",
        language=None,
        source_country=None,
        provider_article_id=compact_hash("finnhub_recommendation", query.upper(), period),
        matched_terms=[query.lower()],
        relevance_score=1.0,
        raw=item,
    )


def newsapi_record(query: str, item: dict) -> HistoricalSourceRecord:
    title = str(item.get("title") or "").strip()
    description = str(item.get("description") or "").strip()
    content = str(item.get("content") or "").strip()
    url = item.get("url")
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    source_name = str(source.get("name") or "NewsAPI")
    published_at = item.get("publishedAt")
    text = " ".join(part for part in [title, description, content] if part).strip()
    matched, relevance = normalized_query_match(query, f"{text} {url or ''}")
    return HistoricalSourceRecord(
        query=query.upper(),
        provider="newsapi_everything",
        source=source_name,
        source_kind="news",
        title=title,
        text=text,
        url=url,
        published_at=published_at,
        fetched_at=utc_now_iso(),
        domain=domain_from_url(url),
        language=None,
        source_country=None,
        provider_article_id=stable_record_id(query=query.upper(), url=url, title=title, published_at=published_at),
        matched_terms=matched,
        relevance_score=relevance,
        raw=item,
    )


def polygon_news_record(query: str, item: dict) -> HistoricalSourceRecord:
    title = str(item.get("title") or "").strip()
    description = str(item.get("description") or "").strip()
    article_url = item.get("article_url")
    published_at = parse_polygon_time(item.get("published_utc"))
    publisher = item.get("publisher") if isinstance(item.get("publisher"), dict) else {}
    source = str(publisher.get("name") or "Polygon")
    text = f"{title}. {description}".strip()
    tickers = [str(t).upper() for t in item.get("tickers", []) if str(t).strip()]
    matched, relevance = normalized_query_match(query, f"{text} {article_url or ''} {' '.join(tickers)}")
    if query.upper() in tickers:
        relevance = 1.0
        if query.lower() not in matched:
            matched.append(query.lower())
    return HistoricalSourceRecord(
        query=query.upper(),
        provider="polygon_ticker_news",
        source=source,
        source_kind="news",
        title=title,
        text=text,
        url=article_url,
        published_at=published_at,
        fetched_at=utc_now_iso(),
        domain=domain_from_url(article_url),
        language=None,
        source_country=None,
        provider_article_id=str(item.get("id") or compact_hash(query, article_url, title, published_at)),
        matched_terms=matched,
        relevance_score=relevance,
        raw=item,
    )


def fetch_alpha_vantage_news(
    *,
    queries: list[str],
    start: date,
    end: date,
    api_key: str,
    limit: int = 200,
    sleep_seconds: float = 12.0,
) -> list[HistoricalSourceRecord]:
    client = JsonApiClient(sleep_seconds=sleep_seconds)
    records: list[HistoricalSourceRecord] = []
    for query in queries:
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": query.upper(),
            "time_from": date_to_av(start),
            "time_to": end.strftime("%Y%m%dT2359"),
            "limit": str(limit),
            "apikey": api_key,
        }
        url = f"{ALPHA_VANTAGE_NEWS_URL}?{urllib.parse.urlencode(params)}"
        payload = client.open_json(url)
        if isinstance(payload, dict):
            feed = payload.get("feed", [])
            records.extend(alpha_vantage_record(query, item) for item in feed if isinstance(item, dict))
            if payload.get("Note") or payload.get("Information"):
                print(f"Alpha Vantage message for {query}: {payload.get('Note') or payload.get('Information')}")
    return dedupe_records(records)


def fetch_finnhub_company_news(
    *,
    queries: list[str],
    start: date,
    end: date,
    api_key: str,
    limit: int = 500,
    sleep_seconds: float = 1.0,
) -> list[HistoricalSourceRecord]:
    client = JsonApiClient(sleep_seconds=sleep_seconds)
    records: list[HistoricalSourceRecord] = []
    for query in queries:
        params = {"symbol": query.upper(), "from": start.isoformat(), "to": end.isoformat(), "token": api_key}
        url = f"{FINNHUB_COMPANY_NEWS_URL}?{urllib.parse.urlencode(params)}"
        payload = client.open_json(url)
        if isinstance(payload, list):
            records.extend(finnhub_news_record(query, item) for item in payload[:limit] if isinstance(item, dict))
    return dedupe_records(records)


def fetch_finnhub_recommendations(
    *,
    queries: list[str],
    api_key: str,
    sleep_seconds: float = 1.0,
) -> list[HistoricalSourceRecord]:
    client = JsonApiClient(sleep_seconds=sleep_seconds)
    records: list[HistoricalSourceRecord] = []
    for query in queries:
        params = {"symbol": query.upper(), "token": api_key}
        url = f"{FINNHUB_RECOMMENDATION_URL}?{urllib.parse.urlencode(params)}"
        payload = client.open_json(url)
        if isinstance(payload, list):
            records.extend(finnhub_recommendation_record(query, item) for item in payload if isinstance(item, dict))
    return dedupe_records(records)


def fetch_newsapi_everything(
    *,
    queries: list[str],
    start: date,
    end: date,
    api_key: str,
    limit: int = 100,
    sleep_seconds: float = 1.0,
    language: str = "en",
) -> list[HistoricalSourceRecord]:
    client = JsonApiClient(sleep_seconds=sleep_seconds)
    records: list[HistoricalSourceRecord] = []
    page_size = min(100, max(1, limit))
    for query in queries:
        params = {
            "q": query,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "language": language,
            "sortBy": "publishedAt",
            "pageSize": str(page_size),
            "apiKey": api_key,
        }
        url = f"{NEWSAPI_EVERYTHING_URL}?{urllib.parse.urlencode(params)}"
        payload = client.open_json(url)
        if isinstance(payload, dict):
            records.extend(newsapi_record(query, item) for item in payload.get("articles", []) if isinstance(item, dict))
            if payload.get("status") == "error":
                print(f"NewsAPI error for {query}: {payload.get('message')}")
    return dedupe_records(records)


def fetch_polygon_ticker_news(
    *,
    queries: list[str],
    start: date,
    end: date,
    api_key: str,
    limit: int = 100,
    sleep_seconds: float = 1.0,
) -> list[HistoricalSourceRecord]:
    client = JsonApiClient(sleep_seconds=sleep_seconds)
    records: list[HistoricalSourceRecord] = []
    for query in queries:
        params = {
            "ticker": query.upper(),
            "published_utc.gte": start.isoformat(),
            "published_utc.lte": end.isoformat(),
            "limit": str(limit),
            "order": "desc",
            "sort": "published_utc",
            "apiKey": api_key,
        }
        url = f"{POLYGON_TICKER_NEWS_URL}?{urllib.parse.urlencode(params)}"
        payload = client.open_json(url)
        if isinstance(payload, dict):
            records.extend(polygon_news_record(query, item) for item in payload.get("results", []) if isinstance(item, dict))
            next_url = payload.get("next_url")
            while next_url and len(records) < limit * max(1, len(queries)):
                sep = "&" if "?" in next_url else "?"
                payload = client.open_json(f"{next_url}{sep}apiKey={urllib.parse.quote(api_key)}")
                if not isinstance(payload, dict):
                    break
                records.extend(polygon_news_record(query, item) for item in payload.get("results", []) if isinstance(item, dict))
                next_url = payload.get("next_url")
    return dedupe_records(records)


PROVIDER_FETCHERS = {
    "alpha_vantage": fetch_alpha_vantage_news,
    "finnhub_news": fetch_finnhub_company_news,
    "finnhub_recommendations": fetch_finnhub_recommendations,
    "newsapi": fetch_newsapi_everything,
    "polygon_news": fetch_polygon_ticker_news,
}


def read_queries_file(path: str | Path) -> list[str]:
    return [
        line.strip().upper()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def write_news_records(records: list[HistoricalSourceRecord], path: str | Path) -> None:
    write_jsonl(records, path)
