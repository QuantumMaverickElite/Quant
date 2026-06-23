from __future__ import annotations

import html
import json
import os
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from .schemas import SourceDocument
from .source_loader import source_reliability


DEFAULT_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT",
    "stock-backtester-market-intelligence/0.1 research-contact-not-set",
)

NON_PRICE_TOPICS = {
    "MARKET",
    "MACRO",
    "ECONOMY",
    "POLITICS",
    "RATES",
    "FED",
    "FOMC",
    "INFLATION",
    "YIELDS",
}


def warn(message: str) -> None:
    print(f"[source-fetch-warning] {message}", file=sys.stderr)


def is_ticker_like(query: str) -> bool:
    query = query.strip().upper()
    if query in NON_PRICE_TOPICS:
        return False
    return bool(query) and len(query) <= 8 and all(ch.isalnum() or ch in {".", "-", "^"} for ch in query)


def http_get(url: str, *, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 20) -> bytes:
    req = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml, application/json, text/html;q=0.8",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def child_text(node: ET.Element, names: Iterable[str]) -> str:
    for name in names:
        child = node.find(name)
        if child is not None and child.text:
            return child.text.strip()

    # Namespace-tolerant fallback.
    wanted = {name.rsplit("}", 1)[-1].lower() for name in names}
    for child in list(node):
        if child.tag.rsplit("}", 1)[-1].lower() in wanted and child.text:
            return child.text.strip()
    return ""


def parse_rss_items(xml_bytes: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(xml_bytes)
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    parsed: list[dict[str, str]] = []
    for item in items:
        title = child_text(item, ["title", "{http://www.w3.org/2005/Atom}title"])
        description = child_text(item, ["description", "summary", "{http://www.w3.org/2005/Atom}summary"])
        link = child_text(item, ["link", "{http://www.w3.org/2005/Atom}link"])
        if not link:
            link_node = item.find("{http://www.w3.org/2005/Atom}link")
            if link_node is not None:
                link = link_node.attrib.get("href", "")
        published = child_text(
            item,
            ["pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"],
        )

        text = strip_html(description)
        if title or text:
            parsed.append(
                {
                    "title": strip_html(title),
                    "text": text,
                    "url": link,
                    "published_at": published,
                }
            )
    return parsed


def yahoo_finance_rss_url(query: str) -> str:
    return f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote_plus(query.upper())}&region=US&lang=en-US"


def google_news_rss_url(query: str) -> str:
    search = f"{query} stock market finance news" if is_ticker_like(query) else f"{query} markets finance news"
    return f"https://news.google.com/rss/search?q={quote_plus(search)}&hl=en-US&gl=US&ceid=US:en"


def fetch_rss_documents(
    *,
    query: str,
    source_name: str,
    url: str,
    max_items: int,
    user_agent: str,
) -> list[SourceDocument]:
    try:
        raw = http_get(url, user_agent=user_agent)
        items = parse_rss_items(raw)
    except (HTTPError, URLError, TimeoutError, ET.ParseError, OSError) as exc:
        warn(f"{source_name} fetch failed for {query}: {exc}")
        return []

    docs: list[SourceDocument] = []
    reliability = source_reliability(source_name)
    for item in items[:max_items]:
        docs.append(
            SourceDocument(
                source=source_name,
                title=item.get("title", ""),
                text=item.get("text", ""),
                url=item.get("url") or None,
                published_at=item.get("published_at") or None,
                reliability=reliability,
            )
        )
    return docs


def fetch_yfinance_documents(
    *,
    query: str,
    max_items: int,
) -> list[SourceDocument]:
    if not is_ticker_like(query):
        return []
    try:
        import yfinance as yf
    except ImportError:
        warn("yfinance news fetch skipped because yfinance is not installed")
        return []

    try:
        raw_news = yf.Ticker(query.upper()).news or []
    except Exception as exc:  # yfinance raises several transport-specific exceptions.
        warn(f"yfinance news fetch failed for {query}: {exc}")
        return []

    docs: list[SourceDocument] = []
    for item in raw_news[:max_items]:
        content = item.get("content") if isinstance(item.get("content"), dict) else {}
        title = item.get("title") or content.get("title") or ""
        summary = item.get("summary") or content.get("summary") or content.get("description") or ""
        publisher = item.get("publisher") or content.get("provider", {}).get("displayName") or "Yahoo Finance/yfinance"
        link = item.get("link")
        if not link and isinstance(content.get("canonicalUrl"), dict):
            link = content["canonicalUrl"].get("url")
        published_at = item.get("providerPublishTime") or content.get("pubDate") or content.get("displayTime")
        docs.append(
            SourceDocument(
                source=f"yfinance news ({publisher})",
                title=strip_html(str(title)),
                text=strip_html(str(summary)),
                url=str(link) if link else None,
                published_at=str(published_at) if published_at else None,
                reliability=0.60,
            )
        )
    return docs


def load_sec_ticker_map(user_agent: str) -> dict[str, dict]:
    url = "https://www.sec.gov/files/company_tickers.json"
    try:
        raw = http_get(url, user_agent=user_agent)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        warn(f"SEC ticker map fetch failed: {exc}")
        return {}
    data = json.loads(raw.decode("utf-8"))
    return {row["ticker"].upper(): row for row in data.values() if row.get("ticker")}


def fetch_sec_documents(
    *,
    query: str,
    max_items: int,
    user_agent: str,
) -> list[SourceDocument]:
    if not is_ticker_like(query):
        return []

    ticker_map = load_sec_ticker_map(user_agent)
    row = ticker_map.get(query.upper())
    if not row:
        return []

    cik = str(row["cik_str"]).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        raw = http_get(url, user_agent=user_agent)
        data = json.loads(raw.decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        warn(f"SEC submissions fetch failed for {query}: {exc}")
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    accession_numbers = recent.get("accessionNumber", [])
    descriptions = recent.get("primaryDocDescription", [])

    docs: list[SourceDocument] = []
    company_name = data.get("name") or row.get("title") or query.upper()
    for idx, form in enumerate(forms):
        if form not in {"8-K", "10-Q", "10-K", "6-K", "20-F", "S-1", "DEF 14A"}:
            continue
        filing_date = filing_dates[idx] if idx < len(filing_dates) else ""
        report_date = report_dates[idx] if idx < len(report_dates) else ""
        accession = accession_numbers[idx] if idx < len(accession_numbers) else ""
        description = descriptions[idx] if idx < len(descriptions) else ""
        title = f"{company_name} SEC filing {form} filed {filing_date}".strip()
        text = (
            f"{query.upper()} filed SEC form {form}. "
            f"Filing date: {filing_date or 'unknown'}. "
            f"Report date: {report_date or 'unknown'}. "
            f"Description: {description or 'not provided'}."
        )
        filing_url = None
        if accession:
            no_dash = accession.replace("-", "")
            filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{no_dash}/{accession}-index.html"
        docs.append(
            SourceDocument(
                source="SEC EDGAR",
                title=title,
                text=text,
                url=filing_url,
                published_at=filing_date or None,
                reliability=0.95,
            )
        )
        if len(docs) >= max_items:
            break
    return docs


def dedupe_documents(docs: list[SourceDocument]) -> list[SourceDocument]:
    seen: set[tuple[str, str, str]] = set()
    out: list[SourceDocument] = []
    for doc in docs:
        key = (doc.source.lower(), (doc.url or "").lower(), doc.title.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(doc)
    return out


def fetch_documents_for_queries(
    queries: list[str],
    *,
    sources: set[str],
    max_items_per_source: int = 8,
    user_agent: str = DEFAULT_USER_AGENT,
) -> list[SourceDocument]:
    docs: list[SourceDocument] = []
    for query in queries:
        query = query.strip().upper()
        if not query:
            continue

        if "yahoo" in sources and is_ticker_like(query):
            docs.extend(
                fetch_rss_documents(
                    query=query,
                    source_name="Yahoo Finance RSS",
                    url=yahoo_finance_rss_url(query),
                    max_items=max_items_per_source,
                    user_agent=user_agent,
                )
            )

        if "yfinance" in sources and is_ticker_like(query):
            docs.extend(fetch_yfinance_documents(query=query, max_items=max_items_per_source))

        if "google" in sources:
            docs.extend(
                fetch_rss_documents(
                    query=query,
                    source_name="Google News RSS",
                    url=google_news_rss_url(query),
                    max_items=max_items_per_source,
                    user_agent=user_agent,
                )
            )

        if "sec" in sources:
            docs.extend(
                fetch_sec_documents(
                    query=query,
                    max_items=max_items_per_source,
                    user_agent=user_agent,
                )
            )

    return dedupe_documents(docs)


def write_documents_jsonl(docs: list[SourceDocument], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(asdict(doc), sort_keys=True) + "\n")


def default_source_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("data/intelligence/raw") / f"live_sources_{stamp}.jsonl"
