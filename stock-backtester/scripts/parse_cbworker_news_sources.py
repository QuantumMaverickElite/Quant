#!/usr/bin/env python3
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timezone

root = Path.home() / "projects/quant/worker_ingest/chromebook/cache/news_sources_raw"
out_dir = Path("outputs/worker_ingest/chromebook")
out_dir.mkdir(parents=True, exist_ok=True)

rows = []

def parse_name(path: Path):
    m = re.match(r"(?P<job_id>\d{8}T\d{6}Z_news_sources)_(?P<provider>.+)_(?P<ticker>[A-Za-z0-9._-]+)\.(json|xml)$", path.name)
    if not m:
        return None, None, None
    return m.group("job_id"), m.group("provider"), m.group("ticker").upper()

def add_row(job_id, provider, ticker, title=None, url=None, source=None, published_at=None, summary=None, raw_file=None):
    if not title and not summary:
        return
    rows.append({
        "job_id": job_id,
        "provider": provider,
        "ticker": ticker,
        "published_at": published_at,
        "title": title,
        "url": url,
        "source": source,
        "summary": summary,
        "raw_file": str(raw_file) if raw_file else None,
    })

for path in sorted(root.rglob("*")):
    if not path.is_file():
        continue

    job_id, provider, ticker = parse_name(path)
    if not job_id:
        continue

    try:
        if path.suffix == ".json":
            data = json.loads(path.read_text(errors="replace"))

            if provider == "alpha_vantage_news":
                for item in data.get("feed", []) or []:
                    add_row(
                        job_id, provider, ticker,
                        title=item.get("title"),
                        url=item.get("url"),
                        source=item.get("source"),
                        published_at=item.get("time_published"),
                        summary=item.get("summary"),
                        raw_file=path,
                    )

            elif provider == "finnhub_company_news":
                if isinstance(data, list):
                    for item in data:
                        add_row(
                            job_id, provider, ticker,
                            title=item.get("headline"),
                            url=item.get("url"),
                            source=item.get("source"),
                            published_at=item.get("datetime"),
                            summary=item.get("summary"),
                            raw_file=path,
                        )

            elif provider == "newsapi_everything":
                for item in data.get("articles", []) or []:
                    src = item.get("source") or {}
                    add_row(
                        job_id, provider, ticker,
                        title=item.get("title"),
                        url=item.get("url"),
                        source=src.get("name"),
                        published_at=item.get("publishedAt"),
                        summary=item.get("description") or item.get("content"),
                        raw_file=path,
                    )

        elif path.suffix == ".xml" and provider == "yahoo_rss":
            tree = ET.parse(path)
            root_xml = tree.getroot()
            channel = root_xml.find("channel")
            if channel is not None:
                for item in channel.findall("item"):
                    add_row(
                        job_id, provider, ticker,
                        title=(item.findtext("title") or "").strip(),
                        url=(item.findtext("link") or "").strip(),
                        source="Yahoo Finance RSS",
                        published_at=(item.findtext("pubDate") or "").strip(),
                        summary=(item.findtext("description") or "").strip(),
                        raw_file=path,
                    )

    except Exception as e:
        print(f"skip {path}: {e}")

df = pd.DataFrame(rows)

if df.empty:
    raise SystemExit("no news rows parsed")

def normalize_published_at(x):
    if x is None or pd.isna(x):
        return None

    # Finnhub returns Unix seconds as int.
    if isinstance(x, (int, float)):
        try:
            return datetime.fromtimestamp(float(x), tz=timezone.utc).isoformat()
        except Exception:
            return str(x)

    x = str(x).strip()
    if not x:
        return None

    # Alpha Vantage format: 20260630T123456
    if len(x) == 15 and x[8] == "T":
        try:
            return datetime.strptime(x, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            return x

    # NewsAPI ISO strings and Yahoo RSS date strings.
    parsed = pd.to_datetime(x, errors="coerce", utc=True)
    if pd.notna(parsed):
        return parsed.isoformat()

    return x

df["published_at"] = df["published_at"].map(normalize_published_at)

# Force all text-ish columns to strings/None so pyarrow does not choke.
for col in ["job_id", "provider", "ticker", "published_at", "title", "url", "source", "summary", "raw_file"]:
    if col in df.columns:
        df[col] = df[col].where(df[col].notna(), None).astype("string")

df = df.drop_duplicates(subset=["provider", "ticker", "title", "url"], keep="first")
df = df.sort_values(["ticker", "provider", "published_at"], na_position="last")

csv_path = out_dir / "cbworker_news_sources.csv"
parquet_path = out_dir / "cbworker_news_sources.parquet"

df.to_csv(csv_path, index=False)
df.to_parquet(parquet_path, index=False)

print(f"rows: {len(df)}")
print(f"tickers: {df['ticker'].nunique()}")
print(f"providers: {', '.join(sorted(df['provider'].unique()))}")
print(f"wrote {csv_path}")
print(f"wrote {parquet_path}")
