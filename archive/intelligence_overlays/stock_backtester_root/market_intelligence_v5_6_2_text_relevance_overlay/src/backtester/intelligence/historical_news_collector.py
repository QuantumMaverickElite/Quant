from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET
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
from .entity_resolver import default_resolver, derive_common_name, is_generic_alias, unique_strings
from .provider_policy import annotate_record_policy, provider_policy, query_relevance


ALPHA_VANTAGE_NEWS_URL = "https://www.alphavantage.co/query"
FINNHUB_COMPANY_NEWS_URL = "https://finnhub.io/api/v1/company-news"
FINNHUB_RECOMMENDATION_URL = "https://finnhub.io/api/v1/stock/recommendation"
NEWSAPI_EVERYTHING_URL = "https://newsapi.org/v2/everything"
POLYGON_TICKER_NEWS_URL = "https://api.polygon.io/v2/reference/news"
MASSIVE_TICKER_NEWS_URL = "https://api.massive.com/v2/reference/news"
YAHOO_FINANCE_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"


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
    return query_relevance(query, text)



def text_entity_relevance(query: str, text: str) -> tuple[list[str], float]:
    """Relevance from human-visible title/body text only.

    Search/RSS URLs often contain the ticker/query as routing metadata. That is
    useful for audit, but it must not be enough to pass relevance gates.
    """
    return normalized_query_match(query, text or "")


def search_source_relevance(query: str, *, text: str, url: object = None) -> tuple[list[str], float, dict]:
    """Score search-style sources without letting URL-only hits dominate.

    The returned score is based on title/body evidence only. URL matches are
    stored for diagnostics but capped out of the pass/fail relevance score.
    """
    body_matched, body_score = text_entity_relevance(query, text)
    url_matched, url_score = normalized_query_match(query, str(url or ""))
    audit = {
        "body_matched_terms": body_matched,
        "body_relevance_score": round(float(body_score), 4),
        "url_matched_terms": url_matched,
        "url_relevance_score": round(float(url_score), 4),
        "url_only_entity_match": bool(url_matched and not body_matched),
    }
    return body_matched, round(float(body_score), 4), audit

def policy_raw(provider: str, raw: dict) -> dict:
    payload = dict(raw)
    payload.setdefault("provider_policy", provider_policy(provider).to_dict())
    return payload


def entity_search_terms(query: str, *, max_terms: int = 3, quote_phrases: bool = True) -> list[str]:
    """Return high-precision search terms while preserving the caller's canonical ticker."""
    canonical = str(query or "").strip().upper()
    if not canonical:
        return []
    terms: list[str] = [canonical]
    record = default_resolver().resolve_query(canonical)
    if record is None:
        return list(unique_strings(tuple(terms)))[:max_terms]

    candidates = [
        record.common_name,
        derive_common_name(record.legal_name),
        record.legal_name,
        *record.aliases,
    ]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if not value or value.upper() == canonical or value.startswith("$"):
            continue
        if len(value) < 4 or is_generic_alias(value):
            continue
        if value.upper() in {canonical, f"${canonical}"}:
            continue
        if quote_phrases and " " in value and not (value.startswith('"') and value.endswith('"')):
            value = f'"{value}"'
        terms.append(value)
    return list(unique_strings(tuple(terms)))[: max(1, max_terms)]


class HttpRequestBudget:
    """Shared cap for real HTTP attempts across provider/query/entity-alias expansion."""

    def __init__(self, max_requests: int | None = None) -> None:
        self.max_requests = int(max_requests) if max_requests is not None else None
        if self.max_requests is not None and self.max_requests < 0:
            raise ValueError("max_requests must be non-negative or None")
        self.attempted = 0
        self.skipped = 0

    @property
    def exhausted(self) -> bool:
        return self.max_requests is not None and self.attempted >= self.max_requests

    @property
    def remaining(self) -> int | None:
        if self.max_requests is None:
            return None
        return max(0, self.max_requests - self.attempted)

    def try_consume(self, label: str) -> bool:
        if self.exhausted:
            self.skipped += 1
            print(f"HTTP request budget exhausted; skipped {label}")
            return False
        self.attempted += 1
        return True


def safe_url_for_log(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
        pairs = []
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() in {"apikey", "api_key", "token"}:
                pairs.append((key, "<redacted>"))
            else:
                pairs.append((key, value))
        query = urllib.parse.urlencode(pairs).replace("%3Credacted%3E", "<redacted>")
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))
    except Exception:
        return "<unprintable-url>"



def strip_html(text: object) -> str:
    raw = str(text or "")
    raw = raw.replace("<![CDATA[", "").replace("]]>", "")
    import html
    import re

    raw = html.unescape(raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def parse_rss_datetime(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, IndexError, OverflowError):
        parsed = pd_datetime_like(text)
        return parsed


def pd_datetime_like(value: str) -> str | None:
    # Tiny dependency-free fallback for common ISO-like RSS dates.
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    return text


def published_in_range(published_at: str | None, start: date, end: date) -> bool:
    if not published_at:
        return True
    try:
        dt = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
        return start <= dt.date() <= end
    except (TypeError, ValueError):
        text = str(published_at)
        if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
            day = text[:10]
            return start.isoformat() <= day <= end.isoformat()
        return True


def rss_child_text(node: ET.Element, names: tuple[str, ...]) -> str:
    wanted = {name.lower() for name in names}
    for child in list(node):
        tag = child.tag.rsplit("}", 1)[-1].lower()
        if tag in wanted:
            if tag == "link" and child.attrib.get("href"):
                return str(child.attrib.get("href") or "").strip()
            if child.text:
                return child.text.strip()
    return ""


def parse_rss_items(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    nodes = root.findall(".//item")
    if not nodes:
        nodes = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    rows: list[dict] = []
    for node in nodes:
        title = strip_html(rss_child_text(node, ("title",)))
        description = strip_html(rss_child_text(node, ("description", "summary")))
        link = rss_child_text(node, ("link",))
        published_raw = rss_child_text(node, ("pubdate", "published", "updated"))
        source = strip_html(rss_child_text(node, ("source",)))
        if not title and not description:
            continue
        rows.append(
            {
                "title": title,
                "description": description,
                "url": link or None,
                "published_raw": published_raw,
                "published_at": parse_rss_datetime(published_raw),
                "source": source,
            }
        )
    return rows


def rss_record(
    query: str,
    item: dict,
    *,
    provider: str,
    source_name: str,
    source_kind: str,
    search_query: str | None = None,
) -> HistoricalSourceRecord:
    title = str(item.get("title") or "").strip()
    description = str(item.get("description") or "").strip()
    url = item.get("url")
    published_at = item.get("published_at")
    text = f"{title}. {description}".strip()
    matched, relevance, relevance_audit = search_source_relevance(query, text=text, url=url)
    raw = dict(item)
    raw["canonical_query"] = query.upper()
    raw["relevance_audit"] = relevance_audit
    if search_query is not None:
        raw["entity_search_query"] = search_query
    return HistoricalSourceRecord(
        query=query.upper(),
        provider=provider,
        source=str(item.get("source") or source_name),
        source_kind=source_kind,
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
        raw=policy_raw(provider, raw),
    )


def rss_relevance_threshold(provider: str, min_relevance_score: float | None) -> float:
    if min_relevance_score is None:
        return float(provider_policy(provider).min_relevance_score)
    return float(min_relevance_score)


def record_passes_relevance(record: HistoricalSourceRecord, threshold: float) -> bool:
    try:
        return float(record.relevance_score or 0.0) >= float(threshold)
    except (TypeError, ValueError):
        return False


class JsonApiClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        sleep_seconds: float = 0.25,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
        user_agent: str = "stock-backtester-market-intelligence/0.1",
        request_budget: HttpRequestBudget | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.sleep_seconds = sleep_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.user_agent = user_agent
        self.request_budget = request_budget

    def open_bytes(self, url: str, *, headers: dict[str, str] | None = None) -> bytes:
        safe_url = safe_url_for_log(url)
        request_headers = {"User-Agent": self.user_agent, **(headers or {})}
        request = urllib.request.Request(url, headers=request_headers)
        last_error: object = None
        for attempt in range(self.max_retries + 1):
            if self.request_budget is not None and not self.request_budget.try_consume(safe_url):
                return b""
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = response.read()
                if self.sleep_seconds > 0:
                    time.sleep(self.sleep_seconds)
                return payload
            except HTTPError as exc:
                detail = self._http_error_detail(exc)
                last_error = detail
                retryable = exc.code in {408, 425, 429, 500, 502, 503, 504}
                if not retryable:
                    print(f"HTTP {exc.code} non-retryable: {detail}")
                    return b""
                if attempt >= self.max_retries:
                    break
                delay = self._retry_delay(exc, attempt)
                print(f"HTTP {exc.code}; retrying in {delay:.1f}s: {detail}")
                time.sleep(delay)
            except (TimeoutError, URLError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                delay = self.backoff_seconds * (2**attempt)
                print(f"Request failed ({exc}); retrying in {delay:.1f}s")
                time.sleep(delay)
        print(f"Request skipped after retries: {last_error}")
        return b""

    def open_json(self, url: str, *, headers: dict[str, str] | None = None) -> dict | list:
        safe_url = safe_url_for_log(url)
        request_headers = {"User-Agent": self.user_agent, **(headers or {})}
        request = urllib.request.Request(url, headers=request_headers)
        last_error: object = None
        for attempt in range(self.max_retries + 1):
            if self.request_budget is not None and not self.request_budget.try_consume(safe_url):
                return {}
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if self.sleep_seconds > 0:
                    time.sleep(self.sleep_seconds)
                return payload
            except HTTPError as exc:
                detail = self._http_error_detail(exc)
                last_error = detail
                retryable = exc.code in {408, 425, 429, 500, 502, 503, 504}
                if not retryable:
                    print(f"HTTP {exc.code} non-retryable: {detail}")
                    return {}
                if attempt >= self.max_retries:
                    break
                delay = self._retry_delay(exc, attempt)
                print(f"HTTP {exc.code}; retrying in {delay:.1f}s: {detail}")
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

    def _http_error_detail(self, exc: HTTPError) -> str:
        body = ""
        try:
            raw = exc.read(4096)
            body = raw.decode("utf-8", errors="replace").strip()
        except Exception:
            body = ""
        if len(body) > 600:
            body = body[:600] + "..."
        reason = getattr(exc, "reason", "") or ""
        if body:
            return f"{exc.code} {reason}; body={body}"
        return f"{exc.code} {reason}"


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
        raw=policy_raw("alpha_vantage_news_sentiment", item),
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
        raw=policy_raw("finnhub_company_news", item),
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
        raw=policy_raw("finnhub_recommendation_trends", item),
    )


def newsapi_record(query: str, item: dict, *, search_query: str | None = None) -> HistoricalSourceRecord:
    title = str(item.get("title") or "").strip()
    description = str(item.get("description") or "").strip()
    content = str(item.get("content") or "").strip()
    url = item.get("url")
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    source_name = str(source.get("name") or "NewsAPI")
    published_at = item.get("publishedAt")
    text = " ".join(part for part in [title, description, content] if part).strip()
    matched, relevance, relevance_audit = search_source_relevance(query, text=text, url=url)
    raw = dict(item)
    raw["relevance_audit"] = relevance_audit
    if search_query is not None:
        raw["entity_search_query"] = search_query
        raw["canonical_query"] = query.upper()
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
        raw=policy_raw("newsapi_everything", raw),
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
        raw=policy_raw("polygon_ticker_news", item),
    )


def massive_news_record(query: str, item: dict) -> HistoricalSourceRecord:
    record = polygon_news_record(query, item)
    return HistoricalSourceRecord(
        query=record.query,
        provider="massive_ticker_news",
        source=record.source,
        source_kind=record.source_kind,
        title=record.title,
        text=record.text,
        url=record.url,
        published_at=record.published_at,
        fetched_at=record.fetched_at,
        domain=record.domain,
        language=record.language,
        source_country=record.source_country,
        provider_article_id=record.provider_article_id,
        matched_terms=record.matched_terms,
        relevance_score=record.relevance_score,
        raw=policy_raw("massive_ticker_news", record.raw),
    )


def fetch_alpha_vantage_news(
    *,
    queries: list[str],
    start: date,
    end: date,
    api_key: str,
    limit: int = 200,
    sleep_seconds: float = 12.0,
    max_retries: int = 3,
    backoff_seconds: float = 2.0,
    timeout_seconds: float = 30.0,
    request_budget: HttpRequestBudget | None = None,
) -> list[HistoricalSourceRecord]:
    client = JsonApiClient(sleep_seconds=sleep_seconds, max_retries=max_retries, backoff_seconds=backoff_seconds, timeout_seconds=timeout_seconds, request_budget=request_budget)
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
    max_retries: int = 3,
    backoff_seconds: float = 2.0,
    timeout_seconds: float = 30.0,
    request_budget: HttpRequestBudget | None = None,
) -> list[HistoricalSourceRecord]:
    client = JsonApiClient(sleep_seconds=sleep_seconds, max_retries=max_retries, backoff_seconds=backoff_seconds, timeout_seconds=timeout_seconds, request_budget=request_budget)
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
    max_retries: int = 3,
    backoff_seconds: float = 2.0,
    timeout_seconds: float = 30.0,
    request_budget: HttpRequestBudget | None = None,
) -> list[HistoricalSourceRecord]:
    client = JsonApiClient(sleep_seconds=sleep_seconds, max_retries=max_retries, backoff_seconds=backoff_seconds, timeout_seconds=timeout_seconds, request_budget=request_budget)
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
    max_retries: int = 3,
    backoff_seconds: float = 2.0,
    timeout_seconds: float = 30.0,
    request_budget: HttpRequestBudget | None = None,
    expand_entity_search: bool = False,
    max_search_aliases: int = 3,
) -> list[HistoricalSourceRecord]:
    client = JsonApiClient(sleep_seconds=sleep_seconds, max_retries=max_retries, backoff_seconds=backoff_seconds, timeout_seconds=timeout_seconds, request_budget=request_budget)
    records: list[HistoricalSourceRecord] = []
    page_size = min(100, max(1, limit))
    for query in queries:
        search_terms = (
            entity_search_terms(query, max_terms=max_search_aliases)
            if expand_entity_search
            else [query]
        )
        for search_query in search_terms:
            params = {
                "q": search_query,
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
                records.extend(
                    newsapi_record(query, item, search_query=search_query)
                    for item in payload.get("articles", [])
                    if isinstance(item, dict)
                )
                if payload.get("status") == "error":
                    print(f"NewsAPI error for {query} search={search_query}: {payload.get('message')}")
    return dedupe_records(records)


def fetch_polygon_ticker_news(
    *,
    queries: list[str],
    start: date,
    end: date,
    api_key: str,
    limit: int = 100,
    sleep_seconds: float = 1.0,
    max_retries: int = 3,
    backoff_seconds: float = 2.0,
    timeout_seconds: float = 30.0,
    request_budget: HttpRequestBudget | None = None,
) -> list[HistoricalSourceRecord]:
    client = JsonApiClient(sleep_seconds=sleep_seconds, max_retries=max_retries, backoff_seconds=backoff_seconds, timeout_seconds=timeout_seconds, request_budget=request_budget)
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


def fetch_massive_ticker_news(
    *,
    queries: list[str],
    start: date,
    end: date,
    api_key: str,
    limit: int = 100,
    sleep_seconds: float = 1.0,
    max_retries: int = 3,
    backoff_seconds: float = 2.0,
    timeout_seconds: float = 30.0,
    request_budget: HttpRequestBudget | None = None,
) -> list[HistoricalSourceRecord]:
    client = JsonApiClient(sleep_seconds=sleep_seconds, max_retries=max_retries, backoff_seconds=backoff_seconds, timeout_seconds=timeout_seconds, request_budget=request_budget)
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
        url = f"{MASSIVE_TICKER_NEWS_URL}?{urllib.parse.urlencode(params)}"
        payload = client.open_json(url)
        if isinstance(payload, dict):
            records.extend(massive_news_record(query, item) for item in payload.get("results", []) if isinstance(item, dict))
            next_url = payload.get("next_url")
            while next_url and len(records) < limit * max(1, len(queries)):
                sep = "&" if "?" in next_url else "?"
                payload = client.open_json(f"{next_url}{sep}apiKey={urllib.parse.quote(api_key)}")
                if not isinstance(payload, dict):
                    break
                records.extend(massive_news_record(query, item) for item in payload.get("results", []) if isinstance(item, dict))
                next_url = payload.get("next_url")
    return dedupe_records(records)



def fetch_yahoo_finance_rss(
    *,
    queries: list[str],
    start: date,
    end: date,
    limit: int = 50,
    sleep_seconds: float = 1.0,
    max_retries: int = 3,
    backoff_seconds: float = 2.0,
    timeout_seconds: float = 30.0,
    request_budget: HttpRequestBudget | None = None,
    min_relevance_score: float | None = None,
) -> list[HistoricalSourceRecord]:
    client = JsonApiClient(sleep_seconds=sleep_seconds, max_retries=max_retries, backoff_seconds=backoff_seconds, timeout_seconds=timeout_seconds, request_budget=request_budget)
    records: list[HistoricalSourceRecord] = []
    threshold = rss_relevance_threshold("rss_yahoo_finance", min_relevance_score)
    skipped_relevance = 0
    for query in queries:
        params = {"s": query.upper(), "region": "US", "lang": "en-US"}
        url = f"{YAHOO_FINANCE_RSS_URL}?{urllib.parse.urlencode(params)}"
        raw = client.open_bytes(url)
        if not raw:
            continue
        try:
            items = parse_rss_items(raw)
        except ET.ParseError as exc:
            print(f"Yahoo Finance RSS parse failed for {query}: {exc}")
            continue
        for item in items[:limit]:
            if published_in_range(item.get("published_at"), start, end):
                record = rss_record(
                    query,
                    item,
                    provider="rss_yahoo_finance",
                    source_name="Yahoo Finance RSS",
                    source_kind="news",
                    search_query=query.upper(),
                )
                if record_passes_relevance(record, threshold):
                    records.append(record)
                else:
                    skipped_relevance += 1
    if skipped_relevance:
        print(f"rss_yahoo: skipped {skipped_relevance} low-relevance rows below {threshold:.2f}")
    return dedupe_records(records)


def fetch_google_news_rss(
    *,
    queries: list[str],
    start: date,
    end: date,
    limit: int = 50,
    sleep_seconds: float = 1.0,
    max_retries: int = 3,
    backoff_seconds: float = 2.0,
    timeout_seconds: float = 30.0,
    request_budget: HttpRequestBudget | None = None,
    expand_entity_search: bool = False,
    max_search_aliases: int = 2,
    min_relevance_score: float | None = None,
) -> list[HistoricalSourceRecord]:
    client = JsonApiClient(sleep_seconds=sleep_seconds, max_retries=max_retries, backoff_seconds=backoff_seconds, timeout_seconds=timeout_seconds, request_budget=request_budget)
    records: list[HistoricalSourceRecord] = []
    threshold = rss_relevance_threshold("rss_google_news", min_relevance_score)
    skipped_relevance = 0
    for query in queries:
        search_terms = entity_search_terms(query, max_terms=max_search_aliases) if expand_entity_search else [query]
        for search_query in search_terms:
            rss_query = f"{search_query} stock market finance news"
            params = {"q": rss_query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
            url = f"{GOOGLE_NEWS_RSS_URL}?{urllib.parse.urlencode(params)}"
            raw = client.open_bytes(url)
            if not raw:
                continue
            try:
                items = parse_rss_items(raw)
            except ET.ParseError as exc:
                print(f"Google News RSS parse failed for {query} search={search_query}: {exc}")
                continue
            for item in items[:limit]:
                if published_in_range(item.get("published_at"), start, end):
                    record = rss_record(
                        query,
                        item,
                        provider="rss_google_news",
                        source_name="Google News RSS",
                        source_kind="news_discovery",
                        search_query=search_query,
                    )
                    if record_passes_relevance(record, threshold):
                        records.append(record)
                    else:
                        skipped_relevance += 1
    if skipped_relevance:
        print(f"rss_google: skipped {skipped_relevance} low-relevance rows below {threshold:.2f}")
    return dedupe_records(records)


PROVIDER_FETCHERS = {
    "alpha_vantage": fetch_alpha_vantage_news,
    "finnhub_news": fetch_finnhub_company_news,
    "finnhub_recommendations": fetch_finnhub_recommendations,
    "newsapi": fetch_newsapi_everything,
    "polygon_news": fetch_polygon_ticker_news,
    "massive_news": fetch_massive_ticker_news,
    "rss_yahoo": fetch_yahoo_finance_rss,
    "rss_google": fetch_google_news_rss,
}


def read_queries_file(path: str | Path) -> list[str]:
    return [
        line.strip().upper()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def write_news_records(records: list[HistoricalSourceRecord], path: str | Path) -> None:
    rows = [annotate_record_policy(record.to_dict()) for record in records]
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
