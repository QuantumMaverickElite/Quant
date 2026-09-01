from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .provider_policy import annotate_record_policy, record_passes_policy


def read_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(rows: Iterable[dict], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _clean(value: object) -> str:
    return str(value or "").strip().lower()


def canonical_url(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except ValueError:
        return raw.lower()
    host = parsed.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+$", "", parsed.path or "")
    ignored = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
    }
    query = urlencode([(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False) if k.lower() not in ignored])
    return urlunparse((parsed.scheme.lower() or "https", host, path, "", query, ""))


def normalized_title(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9 $%.,:;!?+-]", "", text)
    return text[:220]


def published_day(value: object) -> str:
    text = str(value or "")
    if len(text) >= 10:
        return text[:10]
    if len(text) >= 8 and text[:8].isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def source_record_key(record: dict) -> str:
    provider_id = _clean(record.get("provider_article_id"))
    provider = _clean(record.get("provider"))
    if provider_id:
        return f"provider_id:{provider}:{provider_id}"

    url = canonical_url(record.get("url"))
    query = _clean(record.get("query"))
    if url:
        return f"url:{query}:{url}"

    title = normalized_title(record.get("title"))
    published_at = published_day(record.get("published_at"))
    raw_key = "|".join([query, title, published_at])
    digest = hashlib.sha1(raw_key.encode("utf-8")).hexdigest()
    return f"title_day:{digest}"


def soft_duplicate_key(record: dict) -> str:
    query = _clean(record.get("query"))
    title = normalized_title(record.get("title"))
    published_at = published_day(record.get("published_at"))
    raw_key = "|".join([query, title, published_at])
    digest = hashlib.sha1(raw_key.encode("utf-8")).hexdigest()
    return f"title_day:{digest}"


def merge_historical_sources(
    *,
    inputs: list[str | Path],
    out_path: str | Path,
    min_published_at: str | None = None,
    max_published_at: str | None = None,
    min_relevance_score: float | None = None,
    usage: str | None = None,
    apply_source_policy: bool = False,
    audit_csv_path: str | Path | None = None,
) -> tuple[list[dict], dict[str, int]]:
    seen: set[str] = set()
    merged: list[dict] = []
    stats = {
        "input_files": len(inputs),
        "input_rows": 0,
        "kept_rows": 0,
        "duplicate_rows": 0,
        "soft_duplicate_rows": 0,
        "date_filtered_rows": 0,
        "relevance_filtered_rows": 0,
        "policy_filtered_rows": 0,
    }
    audit_rows: list[dict] = []

    for path in inputs:
        for record in read_jsonl(path):
            stats["input_rows"] += 1
            if apply_source_policy:
                record = annotate_record_policy(record, usage=usage)
            published = str(record.get("published_at") or "")
            if min_published_at and published and published < min_published_at:
                stats["date_filtered_rows"] += 1
                continue
            if max_published_at and published and published > max_published_at:
                stats["date_filtered_rows"] += 1
                continue
            if min_relevance_score is not None:
                try:
                    relevance = float(record.get("relevance_score") or 0.0)
                except (TypeError, ValueError):
                    relevance = 0.0
                if relevance < min_relevance_score:
                    stats["relevance_filtered_rows"] += 1
                    continue
            if apply_source_policy and not record_passes_policy(record, usage=usage, min_relevance_score=min_relevance_score):
                stats["policy_filtered_rows"] += 1
                audit_rows.append({"status": "policy_filtered", "key": source_record_key(record), "query": record.get("query"), "provider": record.get("provider"), "title": record.get("title"), "url": record.get("url")})
                continue

            key = source_record_key(record)
            if key in seen:
                stats["duplicate_rows"] += 1
                audit_rows.append({"status": "duplicate", "key": key, "query": record.get("query"), "provider": record.get("provider"), "title": record.get("title"), "url": record.get("url")})
                continue
            soft_key = soft_duplicate_key(record)
            if soft_key in seen:
                stats["soft_duplicate_rows"] += 1
                audit_rows.append({"status": "soft_duplicate", "key": soft_key, "query": record.get("query"), "provider": record.get("provider"), "title": record.get("title"), "url": record.get("url")})
                continue
            seen.add(key)
            seen.add(soft_key)
            merged.append(record)

    merged.sort(key=lambda row: (str(row.get("query") or ""), str(row.get("published_at") or ""), str(row.get("provider") or "")))
    stats["kept_rows"] = len(merged)
    write_jsonl(merged, out_path)
    if audit_csv_path:
        write_audit_csv(audit_rows, audit_csv_path)
    return merged, stats


def write_audit_csv(rows: list[dict], path: str | Path) -> None:
    import csv

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["status", "key", "query", "provider", "title", "url"]
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
