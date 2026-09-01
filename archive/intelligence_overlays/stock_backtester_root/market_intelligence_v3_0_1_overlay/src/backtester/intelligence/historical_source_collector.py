from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


GDELT_DOC_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

QUERY_ALIASES = {
    "PLTR": ["PLTR", "Palantir", "Palantir Technologies"],
    "QQQ": ["QQQ", "Nasdaq 100", "Nasdaq-100"],
    "SPY": ["SPY", "S&P 500", "SPDR S&P 500 ETF"],
    "MARKET": ["stock market", "equity market", "Wall Street", "Nasdaq", "S&P 500"],
}


@dataclass(slots=True)
class HistoricalSourceRecord:
    query: str
    provider: str
    source: str
    source_kind: str
    title: str
    text: str
    url: str | None
    published_at: str | None
    fetched_at: str
    domain: str | None = None
    language: str | None = None
    source_country: str | None = None
    provider_article_id: str | None = None
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_ymd(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def gdelt_datetime(value: date | datetime) -> str:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime(value.year, value.month, value.day)
    return dt.strftime("%Y%m%d%H%M%S")


def date_windows(start: date, end: date, *, window_days: int) -> list[tuple[date, date]]:
    if end < start:
        raise ValueError("end date must be >= start date")
    if window_days < 1:
        raise ValueError("window_days must be >= 1")
    windows: list[tuple[date, date]] = []
    cur = start
    while cur <= end:
        nxt = min(end, cur + timedelta(days=window_days - 1))
        windows.append((cur, nxt))
        cur = nxt + timedelta(days=1)
    return windows


def query_terms(query: str) -> list[str]:
    normalized = query.strip().upper()
    aliases = QUERY_ALIASES.get(normalized, [normalized])
    return [term for term in aliases if term.strip()]


def gdelt_query_for(query: str) -> str:
    terms = query_terms(query)
    if len(terms) == 1:
        return terms[0]
    quoted = [f'"{term}"' if " " in term or "-" in term else term for term in terms]
    return "(" + " OR ".join(quoted) + ")"


def stable_record_id(*, query: str, url: str | None, title: str, published_at: str | None) -> str:
    raw = f"{query}|{url or ''}|{title}|{published_at or ''}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:16]


class GdeltDocClient:
    def __init__(
        self,
        *,
        endpoint: str = GDELT_DOC_ENDPOINT,
        timeout_seconds: float = 30.0,
        sleep_seconds: float = 0.5,
        max_retries: int = 4,
        backoff_seconds: float = 5.0,
    ) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.sleep_seconds = sleep_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def fetch_articles(
        self,
        *,
        query: str,
        start: date,
        end: date,
        max_records: int = 75,
        sort: str = "DateDesc",
    ) -> list[dict]:
        params = {
            "query": gdelt_query_for(query),
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(max_records),
            "sort": sort,
            "startdatetime": gdelt_datetime(start),
            "enddatetime": gdelt_datetime(datetime(end.year, end.month, end.day, 23, 59, 59)),
        }
        url = f"{self.endpoint}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": "stock-backtester-market-intelligence/0.1"})
        payload = self._open_json(request)
        if self.sleep_seconds > 0:
            time.sleep(self.sleep_seconds)
        return list(payload.get("articles", []))

    def _open_json(self, request: urllib.request.Request) -> dict:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                last_error = exc
                retryable = exc.code in {408, 425, 429, 500, 502, 503, 504}
                if not retryable or attempt >= self.max_retries:
                    break
                retry_after = exc.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        delay = self.backoff_seconds * (2**attempt)
                else:
                    delay = self.backoff_seconds * (2**attempt)
                print(f"GDELT HTTP {exc.code}; retrying in {delay:.1f}s")
                time.sleep(delay)
            except (TimeoutError, URLError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                delay = self.backoff_seconds * (2**attempt)
                print(f"GDELT request failed ({exc}); retrying in {delay:.1f}s")
                time.sleep(delay)
        print(f"GDELT request skipped after retries: {last_error}")
        return {"articles": []}


def record_from_gdelt_article(query: str, article: dict) -> HistoricalSourceRecord:
    title = str(article.get("title") or "").strip()
    url = article.get("url")
    domain = article.get("domain")
    published_at = article.get("seendate") or article.get("socialimage") or None
    source = f"GDELT DOC ({domain})" if domain else "GDELT DOC"
    text_parts = [title]
    if domain:
        text_parts.append(f"Source domain: {domain}.")
    if article.get("sourcecountry"):
        text_parts.append(f"Source country: {article.get('sourcecountry')}.")

    return HistoricalSourceRecord(
        query=query.upper(),
        provider="gdelt_doc",
        source=source,
        source_kind="news_discovery",
        title=title,
        text=" ".join(part for part in text_parts if part).strip(),
        url=url,
        published_at=published_at,
        fetched_at=utc_now_iso(),
        domain=domain,
        language=article.get("language"),
        source_country=article.get("sourcecountry"),
        provider_article_id=stable_record_id(query=query.upper(), url=url, title=title, published_at=published_at),
        raw=article,
    )


def dedupe_records(records: Iterable[HistoricalSourceRecord]) -> list[HistoricalSourceRecord]:
    seen: set[str] = set()
    out: list[HistoricalSourceRecord] = []
    for record in records:
        key = record.provider_article_id or stable_record_id(
            query=record.query,
            url=record.url,
            title=record.title,
            published_at=record.published_at,
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out


def fetch_gdelt_historical_sources(
    *,
    queries: list[str],
    start: date,
    end: date,
    window_days: int = 7,
    max_records_per_query_window: int = 75,
    sleep_seconds: float = 0.5,
    max_retries: int = 4,
    backoff_seconds: float = 5.0,
) -> list[HistoricalSourceRecord]:
    client = GdeltDocClient(
        sleep_seconds=sleep_seconds,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
    )
    records: list[HistoricalSourceRecord] = []
    for query in queries:
        for win_start, win_end in date_windows(start, end, window_days=window_days):
            print(f"GDELT fetch query={query.upper()} window={win_start}..{win_end}")
            articles = client.fetch_articles(
                query=query,
                start=win_start,
                end=win_end,
                max_records=max_records_per_query_window,
            )
            records.extend(record_from_gdelt_article(query, article) for article in articles)
    return dedupe_records(records)


def write_jsonl(records: Iterable[HistoricalSourceRecord], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")


def read_queries_file(path: str | Path) -> list[str]:
    return [
        line.strip().upper()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
