from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


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


def source_record_key(record: dict) -> str:
    provider_id = _clean(record.get("provider_article_id"))
    provider = _clean(record.get("provider"))
    if provider_id:
        return f"provider_id:{provider}:{provider_id}"

    url = _clean(record.get("url"))
    query = _clean(record.get("query"))
    title = _clean(record.get("title"))
    published_at = _clean(record.get("published_at"))
    if url:
        return f"url:{query}:{url}"

    raw_key = "|".join([query, title, published_at, provider])
    digest = hashlib.sha1(raw_key.encode("utf-8")).hexdigest()
    return f"fallback:{digest}"


def merge_historical_sources(
    *,
    inputs: list[str | Path],
    out_path: str | Path,
    min_published_at: str | None = None,
    max_published_at: str | None = None,
) -> tuple[list[dict], dict[str, int]]:
    seen: set[str] = set()
    merged: list[dict] = []
    stats = {
        "input_files": len(inputs),
        "input_rows": 0,
        "kept_rows": 0,
        "duplicate_rows": 0,
        "date_filtered_rows": 0,
    }

    for path in inputs:
        for record in read_jsonl(path):
            stats["input_rows"] += 1
            published = str(record.get("published_at") or "")
            if min_published_at and published and published < min_published_at:
                stats["date_filtered_rows"] += 1
                continue
            if max_published_at and published and published > max_published_at:
                stats["date_filtered_rows"] += 1
                continue

            key = source_record_key(record)
            if key in seen:
                stats["duplicate_rows"] += 1
                continue
            seen.add(key)
            merged.append(record)

    merged.sort(key=lambda row: (str(row.get("query") or ""), str(row.get("published_at") or ""), str(row.get("provider") or "")))
    stats["kept_rows"] = len(merged)
    write_jsonl(merged, out_path)
    return merged, stats
