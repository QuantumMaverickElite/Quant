from __future__ import annotations

import argparse
import csv
import json
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from backtester.intelligence.entity_resolver import (
    EntityRecord,
    derive_common_name,
    merge_records,
    split_multi_value,
    static_records,
    unique_strings,
)


SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
DEFAULT_OUT = "data/intelligence/entity_master.csv"


FIELDNAMES = [
    "ticker",
    "cik",
    "legal_name",
    "common_name",
    "aliases",
    "domains",
    "exchange",
    "sector",
    "source",
    "confidence",
    "active",
]


def read_json(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def fetch_sec_company_tickers(*, user_agent: str, timeout_seconds: float = 30.0) -> dict:
    request = urllib.request.Request(
        SEC_COMPANY_TICKERS_URL,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Host": urlparse(SEC_COMPANY_TICKERS_URL).netloc,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def sec_company_tickers_records(payload: dict) -> list[EntityRecord]:
    records: list[EntityRecord] = []
    for row in payload.values():
        ticker = str(row.get("ticker") or "").strip().upper()
        legal_name = str(row.get("title") or "").strip()
        if not ticker or not legal_name:
            continue
        common_name = derive_common_name(legal_name)
        aliases = unique_strings((ticker, f"${ticker}", legal_name, common_name))
        records.append(
            EntityRecord(
                ticker=ticker,
                cik=str(row.get("cik_str") or "").strip(),
                legal_name=legal_name,
                common_name=common_name,
                aliases=aliases,
                source="sec_company_tickers",
                confidence=0.95,
                active=True,
            )
        )
    return records


def manual_alias_records(path: str | Path) -> list[EntityRecord]:
    records: list[EntityRecord] = []
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ticker = str(row.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            legal_name = str(row.get("legal_name") or "").strip()
            common_name = str(row.get("common_name") or "").strip() or derive_common_name(legal_name)
            aliases = unique_strings(split_multi_value(row.get("aliases")) + (legal_name, common_name))
            domains = split_multi_value(row.get("domains") or row.get("domain"))
            records.append(
                EntityRecord(
                    ticker=ticker,
                    cik=str(row.get("cik") or "").strip(),
                    legal_name=legal_name,
                    common_name=common_name,
                    aliases=aliases,
                    domains=domains,
                    exchange=str(row.get("exchange") or "").strip(),
                    sector=str(row.get("sector") or "").strip(),
                    source=str(row.get("source") or "manual_aliases").strip(),
                    confidence=float(row.get("confidence") or 1.0),
                    active=str(row.get("active") or "true").strip().lower() not in {"0", "false", "no", "n"},
                )
            )
    return records


def source_jsonl_records(path: str | Path) -> list[EntityRecord]:
    records: list[EntityRecord] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            ticker = str(row.get("query") or "").strip().upper()
            if not ticker:
                continue
            raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
            title = str(row.get("title") or "").strip()
            text = str(row.get("text") or "").strip()
            candidates = [
                raw.get("companyName"),
                raw.get("company_name"),
                raw.get("name"),
                raw.get("title"),
                title.split(" - ")[0],
            ]
            legal_name = next((str(value).strip() for value in candidates if str(value or "").strip()), "")
            if not legal_name or legal_name.upper() == ticker:
                continue
            common_name = derive_common_name(legal_name)
            aliases = unique_strings((ticker, f"${ticker}", legal_name, common_name))
            records.append(
                EntityRecord(
                    ticker=ticker,
                    cik=str(raw.get("cik") or raw.get("cik_str") or "").strip(),
                    legal_name=legal_name,
                    common_name=common_name,
                    aliases=aliases,
                    source=f"source_jsonl:{Path(path).name}",
                    confidence=0.75 if text else 0.65,
                    active=True,
                )
            )
    return records


def write_entity_master(records: list[EntityRecord], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for record in sorted(records, key=lambda item: item.ticker):
            writer.writerow(
                {
                    "ticker": record.ticker,
                    "cik": record.cik,
                    "legal_name": record.legal_name,
                    "common_name": record.common_name,
                    "aliases": "|".join(record.all_aliases()),
                    "domains": "|".join(record.domains),
                    "exchange": record.exchange,
                    "sector": record.sector,
                    "source": record.source,
                    "confidence": f"{record.confidence:.4f}",
                    "active": str(record.active).lower(),
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the market-intelligence entity master.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output entity master CSV path.")
    parser.add_argument("--sec-company-tickers-json", help="Local SEC company_tickers.json file.")
    parser.add_argument("--fetch-sec-company-tickers", action="store_true", help="Fetch SEC company_tickers.json once.")
    parser.add_argument("--sec-user-agent", help="SEC-compliant user agent for the one-shot fetch.")
    parser.add_argument("--manual-aliases", action="append", default=[], help="CSV with ticker, aliases, optional CIK/name/domain fields.")
    parser.add_argument("--source-jsonl", action="append", default=[], help="Existing source JSONL to mine for ticker/name pairs.")
    parser.add_argument("--no-static-seed", action="store_true", help="Do not include the small built-in alias seed.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records: list[EntityRecord] = []
    if not args.no_static_seed:
        records.extend(static_records())

    if args.sec_company_tickers_json:
        records.extend(sec_company_tickers_records(read_json(args.sec_company_tickers_json)))

    if args.fetch_sec_company_tickers:
        if not args.sec_user_agent:
            raise SystemExit("--sec-user-agent is required with --fetch-sec-company-tickers")
        records.extend(sec_company_tickers_records(fetch_sec_company_tickers(user_agent=args.sec_user_agent)))

    for path in args.source_jsonl:
        records.extend(source_jsonl_records(path))

    for path in args.manual_aliases:
        records.extend(manual_alias_records(path))

    merged = merge_records(records)
    write_entity_master(merged, args.out)
    print(f"Saved entity master: {args.out}")
    print(f"Rows: {len(merged)}")
    sample = [record for record in merged if record.ticker in {"PLTR", "MSFT", "NVDA", "SPY"}]
    for record in sorted(sample, key=lambda item: item.ticker):
        print(f"{record.ticker}: {record.common_name or record.legal_name} aliases={', '.join(record.all_aliases()[:6])}")


if __name__ == "__main__":
    main()
