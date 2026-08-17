from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import hashlib
import re
import pandas as pd


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported table type: {path}")


def canonical_url(url: object) -> str:
    if url is None or pd.isna(url):
        return ""
    raw = str(url).strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))
    except Exception:
        return raw


def clean_text(x: object) -> str:
    if x is None or pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def stable_article_id(row: pd.Series) -> str:
    url = canonical_url(row.get("url"))
    title = clean_text(row.get("title")).lower()
    provider = clean_text(row.get("provider")).lower()
    published_at = clean_text(row.get("published_at"))
    base = url or f"{provider}|{published_at}|{title}"
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()


def build_event_fact_table(
    *,
    news_path: str | Path,
    universe_path: str | Path,
) -> pd.DataFrame:
    news = read_table(news_path).copy()
    universe = read_table(universe_path).copy()

    required = {"ticker", "published_at", "provider", "title"}
    missing = sorted(required - set(news.columns))
    if missing:
        raise ValueError(f"news table missing required columns: {missing}")

    universe["ticker"] = universe["ticker"].astype(str).str.upper()
    universe = universe.drop_duplicates("ticker", keep="first")

    news["ticker"] = news["ticker"].astype(str).str.upper()
    news["published_at"] = pd.to_datetime(news["published_at"], errors="coerce", utc=True)
    news = news[news["published_at"].notna()].copy()

    out = news.merge(
        universe[["ticker", "company_name", "clean_company_name", "cik"]],
        on="ticker",
        how="left",
    )

    out["article_id"] = out.apply(stable_article_id, axis=1)
    out["event_id"] = (
        out["ticker"].astype(str)
        + "_"
        + out["article_id"].astype(str).str.slice(0, 16)
    )

    out["event_time"] = out["published_at"]
    out["event_date"] = out["event_time"].dt.date.astype(str)

    for col in ["source", "summary", "url", "raw_file"]:
        if col not in out.columns:
            out[col] = ""

    out["canonical_url"] = out["url"].map(canonical_url)
    out["title"] = out["title"].map(clean_text)
    out["summary"] = out["summary"].map(clean_text)
    out["text"] = (out["title"] + ". " + out["summary"]).map(clean_text)
    out["text_len"] = out["text"].str.len()

    keep = [
        "event_id",
        "article_id",
        "ticker",
        "company_name",
        "clean_company_name",
        "cik",
        "event_time",
        "event_date",
        "published_at",
        "provider",
        "source",
        "title",
        "summary",
        "url",
        "canonical_url",
        "raw_file",
        "text",
        "text_len",
    ]

    out = out[keep].drop_duplicates(["event_id"], keep="first")
    out = out.sort_values(["ticker", "event_time", "provider"], ascending=[True, True, True])
    return out.reset_index(drop=True)


def write_event_fact_table(df: pd.DataFrame, out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix.lower() == ".parquet":
        df.to_parquet(out_path, index=False)
        df.to_csv(out_path.with_suffix(".csv"), index=False)
    elif out_path.suffix.lower() == ".csv":
        df.to_csv(out_path, index=False)
        df.to_parquet(out_path.with_suffix(".parquet"), index=False)
    else:
        raise ValueError(f"Unsupported output type: {out_path}")
