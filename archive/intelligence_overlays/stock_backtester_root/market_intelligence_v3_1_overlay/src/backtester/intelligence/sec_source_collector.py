from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from .historical_source_collector import HistoricalSourceRecord, parse_ymd, write_jsonl


SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_SUBMISSIONS_FILE_URL = "https://data.sec.gov/submissions/{name}"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"


DEFAULT_FORMS = ("10-K", "10-Q", "8-K", "S-1", "424B", "424B4", "DEF 14A")


@dataclass(slots=True)
class SecCompany:
    ticker: str
    cik: int
    title: str

    @property
    def cik_padded(self) -> str:
        return f"{self.cik:010d}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sec_filing_url(*, cik: int, accession_number: str, primary_document: str | None) -> str:
    accession_clean = accession_number.replace("-", "")
    base = f"{SEC_ARCHIVES_BASE}/{int(cik)}/{accession_clean}"
    if primary_document:
        return f"{base}/{primary_document}"
    return base


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return parse_ymd(value[:10])
    except ValueError:
        return None


class SecEdgarClient:
    def __init__(
        self,
        *,
        user_agent: str,
        sleep_seconds: float = 0.25,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
    ) -> None:
        self.user_agent = user_agent
        self.sleep_seconds = sleep_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def open_json(self, url: str) -> dict:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": urlparse(url).netloc,
            },
        )
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    payload = response.read()
                    if response.headers.get("Content-Encoding") == "gzip":
                        import gzip

                        payload = gzip.decompress(payload)
                    if self.sleep_seconds > 0:
                        time.sleep(self.sleep_seconds)
                    return json.loads(payload.decode("utf-8"))
            except HTTPError as exc:
                last_error = exc
                retryable = exc.code in {408, 425, 429, 500, 502, 503, 504}
                if not retryable or attempt >= self.max_retries:
                    break
                delay = self.backoff_seconds * (2**attempt)
                print(f"SEC HTTP {exc.code}; retrying in {delay:.1f}s")
                time.sleep(delay)
            except (TimeoutError, URLError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                delay = self.backoff_seconds * (2**attempt)
                print(f"SEC request failed ({exc}); retrying in {delay:.1f}s")
                time.sleep(delay)
        raise RuntimeError(f"SEC request failed after retries: {url} ({last_error})")

    def company_tickers(self) -> dict[str, SecCompany]:
        payload = self.open_json(SEC_COMPANY_TICKERS_URL)
        out: dict[str, SecCompany] = {}
        for row in payload.values():
            ticker = str(row["ticker"]).upper()
            out[ticker] = SecCompany(ticker=ticker, cik=int(row["cik_str"]), title=str(row["title"]))
        return out

    def submissions(self, company: SecCompany) -> dict:
        return self.open_json(SEC_SUBMISSIONS_URL.format(cik=company.cik_padded))

    def older_submission_file(self, name: str) -> dict:
        return self.open_json(SEC_SUBMISSIONS_FILE_URL.format(name=name))


def table_from_sec_recent(recent: dict) -> list[dict]:
    if not recent:
        return []
    keys = list(recent.keys())
    n = max((len(recent.get(key, [])) for key in keys), default=0)
    rows: list[dict] = []
    for idx in range(n):
        row = {}
        for key in keys:
            values = recent.get(key, [])
            row[key] = values[idx] if idx < len(values) else None
        rows.append(row)
    return rows


def form_matches(form: str | None, allowed_forms: set[str]) -> bool:
    if not allowed_forms:
        return True
    value = str(form or "").upper()
    return value in allowed_forms or any(value.startswith(prefix.rstrip("*")) for prefix in allowed_forms if prefix.endswith("*"))


def sec_record_from_filing(*, company: SecCompany, filing: dict) -> HistoricalSourceRecord:
    form = str(filing.get("form") or "")
    filing_date = str(filing.get("filingDate") or "")
    report_date = str(filing.get("reportDate") or "")
    accession = str(filing.get("accessionNumber") or "")
    primary_document = filing.get("primaryDocument")
    description = str(filing.get("primaryDocDescription") or "").strip()
    items = str(filing.get("items") or "").strip()
    title_parts = [company.title, form]
    if report_date:
        title_parts.append(f"report date {report_date}")
    title = " - ".join(part for part in title_parts if part)
    text = (
        f"{company.title} ({company.ticker}) filed SEC form {form}. "
        f"Filing date: {filing_date}. Report date: {report_date or 'unknown'}. "
        f"Description: {description or 'none'}. Items: {items or 'none'}."
    )
    url = sec_filing_url(cik=company.cik, accession_number=accession, primary_document=primary_document)

    return HistoricalSourceRecord(
        query=company.ticker,
        provider="sec_edgar_submissions",
        source="SEC EDGAR",
        source_kind="filing",
        title=title,
        text=text,
        url=url,
        published_at=filing_date,
        fetched_at=utc_now_iso(),
        domain="sec.gov",
        language="English",
        source_country="United States",
        provider_article_id=accession or None,
        matched_terms=[company.ticker.lower(), company.title.lower()],
        relevance_score=1.0,
        raw=filing,
    )


def fetch_sec_historical_sources(
    *,
    tickers: list[str],
    start: date,
    end: date,
    forms: tuple[str, ...] = DEFAULT_FORMS,
    user_agent: str,
    include_older_files: bool = True,
    sleep_seconds: float = 0.25,
) -> list[HistoricalSourceRecord]:
    client = SecEdgarClient(user_agent=user_agent, sleep_seconds=sleep_seconds)
    companies = client.company_tickers()
    allowed_forms = {form.upper() for form in forms}
    records: list[HistoricalSourceRecord] = []

    for ticker in tickers:
        symbol = ticker.upper()
        company = companies.get(symbol)
        if company is None:
            print(f"SEC ticker not found: {symbol}")
            continue
        print(f"SEC fetch ticker={symbol} cik={company.cik_padded} title={company.title}")
        payload = client.submissions(company)
        recent_rows = table_from_sec_recent(payload.get("filings", {}).get("recent", {}))
        all_rows = list(recent_rows)

        if include_older_files:
            for file_row in payload.get("filings", {}).get("files", []):
                name = file_row.get("name")
                if not name:
                    continue
                older = client.older_submission_file(str(name))
                all_rows.extend(table_from_sec_recent(older))

        kept = 0
        for row in all_rows:
            filing_date = parse_date(row.get("filingDate"))
            if filing_date is None or filing_date < start or filing_date > end:
                continue
            if not form_matches(row.get("form"), allowed_forms):
                continue
            records.append(sec_record_from_filing(company=company, filing=row))
            kept += 1
        print(f"SEC kept {kept} filings for {symbol}")

    return records


def write_sec_records(records: list[HistoricalSourceRecord], path: str | Path) -> None:
    write_jsonl(records, path)
