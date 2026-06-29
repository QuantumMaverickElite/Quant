#!/usr/bin/env python3
"""Bounded SQLite cache for live/intraday market intelligence evidence.

The cache stores deduped article metadata, optional compressed raw payloads, entity links,
sentiment/evidence scores, and compact ticker feature snapshots. It is designed to avoid
rescoring the same article repeatedly while keeping raw payload retention bounded.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1

DDL = r"""
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS articles (
  article_hash TEXT PRIMARY KEY,
  provider TEXT,
  source_kind TEXT,
  source_name TEXT,
  url TEXT,
  title TEXT,
  published_at TEXT,
  discovered_at TEXT NOT NULL,
  query TEXT,
  ticker_hint TEXT,
  body_hash TEXT,
  raw_json_gz BLOB,
  raw_expires_at TEXT,
  official_flag INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_discovered ON articles(discovered_at);
CREATE INDEX IF NOT EXISTS idx_articles_provider ON articles(provider);
CREATE INDEX IF NOT EXISTS idx_articles_query ON articles(query);

CREATE TABLE IF NOT EXISTS article_entities (
  article_hash TEXT NOT NULL,
  ticker TEXT NOT NULL,
  relevance_score REAL,
  title_entity_gate_pass INTEGER,
  entity_score REAL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(article_hash, ticker),
  FOREIGN KEY(article_hash) REFERENCES articles(article_hash) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entities_ticker ON article_entities(ticker);

CREATE TABLE IF NOT EXISTS article_scores (
  article_hash TEXT PRIMARY KEY,
  sentiment_score REAL,
  sentiment_label TEXT,
  event_type TEXT,
  novelty_score REAL,
  evidence_score REAL,
  model_version TEXT,
  scored_at TEXT NOT NULL,
  FOREIGN KEY(article_hash) REFERENCES articles(article_hash) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ticker_feature_snapshots (
  as_of TEXT NOT NULL,
  ticker TEXT NOT NULL,
  window_minutes INTEGER NOT NULL,
  article_count INTEGER NOT NULL DEFAULT 0,
  unique_provider_count INTEGER NOT NULL DEFAULT 0,
  sentiment_mean REAL,
  sentiment_weighted REAL,
  official_count INTEGER NOT NULL DEFAULT 0,
  max_relevance REAL,
  novelty_mean REAL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(as_of, ticker, window_minutes)
);

CREATE INDEX IF NOT EXISTS idx_feature_ticker_asof ON ticker_feature_snapshots(ticker, as_of);
"""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utc_now()).astimezone(timezone.utc).isoformat()


def parse_dt(value: Any) -> datetime | None:
    if value in (None, "", "None"):
        return None
    if isinstance(value, (int, float)):
        try:
            # Assume unix seconds for realistic timestamps, ms for huge values.
            v = float(value)
            if v > 10_000_000_000:
                v /= 1000.0
            return datetime.fromtimestamp(v, tz=timezone.utc)
        except Exception:
            return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def first_nonempty(obj: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        cur: Any = obj
        ok = True
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and cur not in (None, "", [], {}):
            return cur
    return None


def normalize_text(value: Any, max_len: int = 5000) -> str:
    if value is None:
        return ""
    s = str(value).replace("\x00", " ").strip()
    return " ".join(s.split())[:max_len]


def article_hash(rec: dict[str, Any]) -> str:
    provider = normalize_text(first_nonempty(rec, ["provider", "source", "source.provider"]), 200).lower()
    url = normalize_text(first_nonempty(rec, ["url", "link", "article_url", "raw.url"]), 2000).lower()
    title = normalize_text(first_nonempty(rec, ["title", "headline", "summary", "raw.title", "raw.headline"]), 1000).lower()
    published = first_nonempty(rec, ["published_at", "datetime", "date", "time_published", "raw.published_at", "raw.datetime"])
    dt = parse_dt(published)
    date_key = dt.date().isoformat() if dt else ""
    key = "\n".join([provider, url, title, date_key])
    if not url and not title:
        key = json.dumps(rec, sort_keys=True, default=str)[:5000]
    return hashlib.sha256(key.encode("utf-8", "ignore")).hexdigest()


def body_hash(rec: dict[str, Any]) -> str | None:
    body = normalize_text(first_nonempty(rec, ["body", "content", "description", "summary", "raw.body", "raw.content", "raw.description"]), 20000)
    if not body:
        return None
    return hashlib.sha256(body.encode("utf-8", "ignore")).hexdigest()


def gz_json(rec: dict[str, Any]) -> bytes:
    return gzip.compress(json.dumps(rec, sort_keys=True, default=str).encode("utf-8"), compresslevel=6)


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(DDL)
    con.execute("INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)", ("schema_version", str(SCHEMA_VERSION)))
    con.commit()
    return con


def infer_source_kind(rec: dict[str, Any]) -> str:
    provider = str(first_nonempty(rec, ["provider", "source", "source.provider"]) or "").lower()
    source_kind = str(first_nonempty(rec, ["source_kind", "kind", "policy.source_kind"]) or "").lower()
    if source_kind:
        return source_kind
    if "sec" in provider or "edgar" in provider:
        return "official_filing"
    if "ir" in provider or "company" in provider:
        return "company_official"
    if "recommendation" in provider:
        return "market_recommendation"
    return "media_news"


def official_flag_for(source_kind: str, rec: dict[str, Any]) -> int:
    raw = first_nonempty(rec, ["official_flag", "is_official", "policy.official_source", "official_source"])
    if isinstance(raw, bool):
        return int(raw)
    if str(raw).lower() in {"1", "true", "yes"}:
        return 1
    return int(source_kind in {"official_filing", "company_official", "sec_filing"})


def tickers_from_record(rec: dict[str, Any]) -> list[str]:
    vals: list[Any] = []
    for key in ["ticker", "query", "symbol", "symbols", "tickers", "entities", "resolved_ticker"]:
        v = first_nonempty(rec, [key])
        if v is not None:
            vals.append(v)
    out: list[str] = []
    for v in vals:
        if isinstance(v, str):
            pieces = [v]
            if "," in v:
                pieces = v.split(",")
        elif isinstance(v, list):
            pieces = v
        else:
            pieces = [v]
        for x in pieces:
            if isinstance(x, dict):
                x = x.get("ticker") or x.get("symbol") or x.get("resolved_ticker")
            s = str(x or "").strip().upper().lstrip("$")
            if s and 1 <= len(s) <= 8 and s.replace(".", "").replace("-", "").isalnum() and s not in out:
                out.append(s)
    return out[:20]


def float_or_none(v: Any) -> float | None:
    try:
        if v in (None, "", "None"):
            return None
        return float(v)
    except Exception:
        return None


def insert_record(con: sqlite3.Connection, rec: dict[str, Any], raw_ttl_days: int, keep_raw: bool, keep_raw_official: bool) -> tuple[bool, str]:
    now = utc_now()
    now_s = iso(now)
    h = article_hash(rec)
    provider = normalize_text(first_nonempty(rec, ["provider", "source", "source.provider"]), 200)
    source_name = normalize_text(first_nonempty(rec, ["source_name", "source.name", "raw.source", "publisher"]), 300)
    source_kind = infer_source_kind(rec)
    official = official_flag_for(source_kind, rec)
    url = normalize_text(first_nonempty(rec, ["url", "link", "article_url", "raw.url"]), 2000)
    title = normalize_text(first_nonempty(rec, ["title", "headline", "summary", "raw.title", "raw.headline"]), 1000)
    published_dt = parse_dt(first_nonempty(rec, ["published_at", "datetime", "date", "time_published", "raw.published_at", "raw.datetime"]))
    published_s = iso(published_dt) if published_dt else None
    query = normalize_text(first_nonempty(rec, ["query", "ticker", "symbol"]), 50).upper() or None
    tickers = tickers_from_record(rec)
    ticker_hint = tickers[0] if tickers else query
    bh = body_hash(rec)

    raw_blob = None
    raw_expires_at = None
    if keep_raw or (keep_raw_official and official):
        raw_blob = gz_json(rec)
        if not official:
            raw_expires_at = iso(now + timedelta(days=raw_ttl_days))

    cur = con.execute("SELECT article_hash FROM articles WHERE article_hash=?", (h,))
    existed = cur.fetchone() is not None

    con.execute(
        """
        INSERT INTO articles(article_hash, provider, source_kind, source_name, url, title, published_at, discovered_at,
                             query, ticker_hint, body_hash, raw_json_gz, raw_expires_at, official_flag, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(article_hash) DO UPDATE SET
            provider=COALESCE(excluded.provider, articles.provider),
            source_kind=COALESCE(excluded.source_kind, articles.source_kind),
            source_name=COALESCE(excluded.source_name, articles.source_name),
            url=COALESCE(excluded.url, articles.url),
            title=COALESCE(excluded.title, articles.title),
            published_at=COALESCE(excluded.published_at, articles.published_at),
            query=COALESCE(excluded.query, articles.query),
            ticker_hint=COALESCE(excluded.ticker_hint, articles.ticker_hint),
            body_hash=COALESCE(excluded.body_hash, articles.body_hash),
            raw_json_gz=COALESCE(excluded.raw_json_gz, articles.raw_json_gz),
            raw_expires_at=COALESCE(excluded.raw_expires_at, articles.raw_expires_at),
            official_flag=MAX(excluded.official_flag, articles.official_flag),
            updated_at=excluded.updated_at
        """,
        (h, provider, source_kind, source_name, url, title, published_s, now_s, query, ticker_hint, bh, raw_blob, raw_expires_at, official, now_s, now_s),
    )

    relevance = float_or_none(first_nonempty(rec, ["relevance_score", "entity_relevance", "raw.relevance_score"]))
    title_gate = first_nonempty(rec, ["title_entity_gate_pass", "raw.title_entity_gate_pass"])
    title_gate_i = None if title_gate is None else int(str(title_gate).lower() in {"1", "true", "yes"})
    entity_score = float_or_none(first_nonempty(rec, ["entity_score", "resolver_score", "raw.entity_score"]))
    for t in tickers:
        con.execute(
            """
            INSERT INTO article_entities(article_hash, ticker, relevance_score, title_entity_gate_pass, entity_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(article_hash, ticker) DO UPDATE SET
                relevance_score=COALESCE(excluded.relevance_score, article_entities.relevance_score),
                title_entity_gate_pass=COALESCE(excluded.title_entity_gate_pass, article_entities.title_entity_gate_pass),
                entity_score=COALESCE(excluded.entity_score, article_entities.entity_score)
            """,
            (h, t, relevance, title_gate_i, entity_score, now_s),
        )

    sentiment = float_or_none(first_nonempty(rec, ["sentiment_score", "model_sentiment_score", "raw.model_sentiment_score", "raw.sentiment_score"]))
    sentiment_label = normalize_text(first_nonempty(rec, ["sentiment_label", "raw.sentiment_label"]), 50) or None
    event_type = normalize_text(first_nonempty(rec, ["event_type", "claim_type", "raw.event_type"]), 80) or None
    novelty = float_or_none(first_nonempty(rec, ["novelty_score", "raw.novelty_score"]))
    evidence = float_or_none(first_nonempty(rec, ["evidence_score", "source_trust_score", "raw.evidence_score"]))
    model_version = normalize_text(first_nonempty(rec, ["sentiment_model", "model_version", "raw.sentiment_model"]), 100) or None
    if any(v is not None for v in [sentiment, sentiment_label, event_type, novelty, evidence, model_version]):
        con.execute(
            """
            INSERT INTO article_scores(article_hash, sentiment_score, sentiment_label, event_type, novelty_score, evidence_score, model_version, scored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(article_hash) DO UPDATE SET
                sentiment_score=COALESCE(excluded.sentiment_score, article_scores.sentiment_score),
                sentiment_label=COALESCE(excluded.sentiment_label, article_scores.sentiment_label),
                event_type=COALESCE(excluded.event_type, article_scores.event_type),
                novelty_score=COALESCE(excluded.novelty_score, article_scores.novelty_score),
                evidence_score=COALESCE(excluded.evidence_score, article_scores.evidence_score),
                model_version=COALESCE(excluded.model_version, article_scores.model_version),
                scored_at=excluded.scored_at
            """,
            (h, sentiment, sentiment_label, event_type, novelty, evidence, model_version, now_s),
        )

    return (not existed), h


def ingest_jsonl(db: Path, jsonl: Path, raw_ttl_days: int, keep_raw: bool, keep_raw_official: bool, commit_every: int = 500) -> None:
    con = connect(db)
    total = inserted = dupes = bad = 0
    with jsonl.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                rec = json.loads(line)
                if not isinstance(rec, dict):
                    raise ValueError("record is not object")
            except Exception:
                bad += 1
                continue
            is_new, _ = insert_record(con, rec, raw_ttl_days, keep_raw, keep_raw_official)
            inserted += int(is_new)
            dupes += int(not is_new)
            if total % commit_every == 0:
                con.commit()
    con.commit()
    con.close()
    print(f"ingested={total} inserted_new={inserted} duplicates_updated={dupes} bad_lines={bad} db={db}")


def expire(db: Path, raw_ttl_days: int, feature_retention_days: int, max_mb: float | None) -> None:
    con = connect(db)
    now = utc_now()
    now_s = iso(now)
    raw_cutoff = iso(now - timedelta(days=raw_ttl_days))
    feature_cutoff = iso(now - timedelta(days=feature_retention_days))

    # Drop expired raw payloads but preserve article metadata/scores.
    cur = con.execute(
        """
        UPDATE articles
        SET raw_json_gz=NULL, raw_expires_at=NULL, updated_at=?
        WHERE raw_json_gz IS NOT NULL
          AND official_flag=0
          AND (raw_expires_at IS NOT NULL AND raw_expires_at < ?)
        """,
        (now_s, now_s),
    )
    raw_dropped = cur.rowcount

    cur = con.execute("DELETE FROM ticker_feature_snapshots WHERE as_of < ?", (feature_cutoff,))
    features_deleted = cur.rowcount

    con.commit()
    con.execute("VACUUM")
    con.close()

    size = db.stat().st_size if db.exists() else 0
    print(f"expired_raw_payloads={raw_dropped} deleted_old_features={features_deleted} size={size/1024/1024:.2f} MiB")

    if max_mb is not None and size > max_mb * 1024 * 1024:
        print(f"WARNING cache above budget: {size/1024/1024:.2f} MiB > {max_mb:.2f} MiB")
        print("Run with shorter --raw-ttl-days, avoid --keep-raw, or archive/export old records.")


def stats(db: Path) -> None:
    con = connect(db)
    tables = ["articles", "article_entities", "article_scores", "ticker_feature_snapshots"]
    print(f"db={db} size={db.stat().st_size/1024/1024:.2f} MiB" if db.exists() else f"db={db}")
    for t in tables:
        n = con.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
        print(f"{t:28s} {n:12,d}")
    rows = con.execute(
        """
        SELECT provider, COUNT(*) AS n
        FROM articles
        GROUP BY provider
        ORDER BY n DESC
        LIMIT 20
        """
    ).fetchall()
    if rows:
        print("\nproviders")
        for r in rows:
            print(f"{str(r['provider']):28s} {r['n']:12,d}")
    rows = con.execute(
        """
        SELECT e.ticker, COUNT(*) AS n
        FROM article_entities e
        GROUP BY e.ticker
        ORDER BY n DESC
        LIMIT 20
        """
    ).fetchall()
    if rows:
        print("\ntop tickers")
        for r in rows:
            print(f"{r['ticker']:10s} {r['n']:12,d}")
    con.close()


def export_features(db: Path, out: Path, since: str | None) -> None:
    con = connect(db)
    where = ""
    params: list[Any] = []
    if since:
        dt = parse_dt(since)
        if not dt:
            raise SystemExit(f"invalid --since: {since}")
        where = "WHERE COALESCE(a.published_at, a.discovered_at) >= ?"
        params.append(iso(dt))
    sql = f"""
    SELECT
      COALESCE(a.published_at, a.discovered_at) AS as_of,
      e.ticker,
      a.provider,
      a.source_kind,
      a.official_flag,
      e.relevance_score,
      e.title_entity_gate_pass,
      s.sentiment_score,
      s.sentiment_label,
      s.event_type,
      s.novelty_score,
      s.evidence_score,
      a.article_hash,
      a.title,
      a.url
    FROM articles a
    LEFT JOIN article_entities e ON a.article_hash=e.article_hash
    LEFT JOIN article_scores s ON a.article_hash=s.article_hash
    {where}
    ORDER BY as_of, ticker
    """
    rows = con.execute(sql, params).fetchall()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        cols = rows[0].keys() if rows else ["as_of", "ticker", "provider", "source_kind", "official_flag", "relevance_score", "sentiment_score", "article_hash", "title", "url"]
        f.write(",".join(cols) + "\n")
        for r in rows:
            vals = []
            for c in r.keys():
                v = r[c]
                s = "" if v is None else str(v)
                if any(ch in s for ch in [",", "\"", "\n"]):
                    s = '"' + s.replace('"', '""') + '"'
                vals.append(s)
            f.write(",".join(vals) + "\n")
    con.close()
    print(f"exported_rows={len(rows)} out={out}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_db(p: argparse.ArgumentParser) -> None:
        p.add_argument("--db", default="data/intelligence/cache/live_intelligence.sqlite", help="SQLite cache path")

    p = sub.add_parser("init", help="Create/update cache schema")
    add_db(p)

    p = sub.add_parser("ingest-jsonl", help="Ingest provider JSONL into deduped cache")
    add_db(p)
    p.add_argument("--jsonl", required=True)
    p.add_argument("--raw-ttl-days", type=int, default=14)
    p.add_argument("--keep-raw", action="store_true", help="Store compressed raw JSON until TTL. Default false.")
    p.add_argument("--keep-raw-official", action="store_true", help="Store official raw JSON longer")
    p.add_argument("--commit-every", type=int, default=500)

    p = sub.add_parser("expire", help="Drop expired raw payloads and old features")
    add_db(p)
    p.add_argument("--raw-ttl-days", type=int, default=14)
    p.add_argument("--feature-retention-days", type=int, default=730)
    p.add_argument("--max-mb", type=float, default=2048.0)

    p = sub.add_parser("stats", help="Print cache stats")
    add_db(p)

    p = sub.add_parser("export-features", help="Export article/entity/score features to compact CSV")
    add_db(p)
    p.add_argument("--out", required=True)
    p.add_argument("--since")

    args = ap.parse_args()
    db = Path(args.db)
    if args.cmd == "init":
        con = connect(db)
        con.close()
        print(f"initialized {db}")
    elif args.cmd == "ingest-jsonl":
        ingest_jsonl(db, Path(args.jsonl), args.raw_ttl_days, args.keep_raw, args.keep_raw_official, args.commit_every)
    elif args.cmd == "expire":
        expire(db, args.raw_ttl_days, args.feature_retention_days, args.max_mb)
    elif args.cmd == "stats":
        stats(db)
    elif args.cmd == "export-features":
        export_features(db, Path(args.out), args.since)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
