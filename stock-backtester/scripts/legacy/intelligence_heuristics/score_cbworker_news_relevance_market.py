#!/usr/bin/env python3
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import hashlib
import re
import pandas as pd

news_path = Path("outputs/worker_ingest/chromebook/cbworker_news_sources.parquet")
universe_path = Path("data/reference/ticker_universe_sec.parquet")
out_dir = Path("outputs/worker_ingest/chromebook")
out_dir.mkdir(parents=True, exist_ok=True)

news = pd.read_parquet(news_path)
universe = pd.read_parquet(universe_path)

universe["ticker"] = universe["ticker"].astype(str).str.upper()
meta = universe.set_index("ticker").to_dict("index")

stopwords = {
    "the", "and", "for", "with", "from", "corp", "corporation", "inc", "incorporated",
    "company", "companies", "holdings", "holding", "group", "limited", "ltd", "plc",
    "class", "common", "stock", "trust", "fund", "etf", "acquisition"
}

provider_prior = {
    "finnhub_company_news": 0.30,
    "yahoo_rss": 0.28,
    "newsapi_everything": 0.22,
    "alpha_vantage_news": 0.18,
}

spam_terms = [
    "class action",
    "shareholder alert",
    "securities fraud",
    "deadline alert",
    "lost money",
    "lawsuit",
    "levi & korsinsky",
    "glancy prongay",
    "rosen law",
    "pomerantz",
    "investigation alert",
]

def safe_str(x):
    if x is None or pd.isna(x):
        return ""
    return str(x)

def canonical_url(url):
    url = safe_str(url).strip()
    if not url:
        return ""
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))
    except Exception:
        return url

def normalize_text(x):
    x = safe_str(x).lower()
    x = re.sub(r"[^a-z0-9 ]+", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x

def contains_ticker(text, ticker):
    text_u = safe_str(text).upper()
    ticker = safe_str(ticker).upper()
    if not ticker:
        return False
    pat = re.compile(rf"(?<![A-Z0-9]){re.escape(ticker)}(?![A-Z0-9])")
    return bool(pat.search(text_u))

def useful_company_tokens(clean_name):
    toks = []
    for t in normalize_text(clean_name).split():
        if len(t) >= 4 and t not in stopwords:
            toks.append(t)
    return toks

def phrase_match(text_norm, phrase_norm):
    if not phrase_norm:
        return False
    if len(phrase_norm) < 4:
        return False
    return phrase_norm in text_norm

def article_key(row):
    url = canonical_url(row.get("url"))
    title = normalize_text(row.get("title"))
    base = url or title
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:16]

news["ticker"] = news["ticker"].astype(str).str.upper()
news["canonical_url"] = news["url"].map(canonical_url)
news["normalized_title"] = news["title"].map(normalize_text)
news["article_key"] = news.apply(article_key, axis=1)

provider_counts = news.groupby("article_key")["provider"].nunique().rename("provider_count")
news = news.merge(provider_counts, on="article_key", how="left")

rows = []

now = pd.Timestamp.now(tz="UTC")

for _, row in news.iterrows():
    ticker = safe_str(row.get("ticker")).upper()
    provider = safe_str(row.get("provider"))

    title = safe_str(row.get("title"))
    summary = safe_str(row.get("summary"))
    url = safe_str(row.get("url"))

    title_norm = normalize_text(title)
    summary_norm = normalize_text(summary)
    full_norm = normalize_text(title + " " + summary)

    m = meta.get(ticker, {})
    company_name = safe_str(m.get("company_name"))
    clean_company_name = safe_str(m.get("clean_company_name"))
    cik = safe_str(m.get("cik"))

    company_tokens = useful_company_tokens(clean_company_name)
    company_phrase_hit_title = phrase_match(title_norm, normalize_text(clean_company_name))
    company_phrase_hit_summary = phrase_match(summary_norm, normalize_text(clean_company_name))

    token_hits_title = sum(1 for t in company_tokens if t in title_norm)
    token_hits_summary = sum(1 for t in company_tokens if t in summary_norm)

    ticker_in_title = contains_ticker(title, ticker)
    ticker_in_summary = contains_ticker(summary, ticker)
    ticker_in_url = ticker in url.upper()

    short_or_ambiguous = len(ticker) <= 3

    text_l = (title + " " + summary).lower()
    legal_spam = any(term in text_l for term in spam_terms)

    score = provider_prior.get(provider, 0.20)

    if ticker_in_title:
        score += 0.25 if short_or_ambiguous else 0.33
    if ticker_in_summary:
        score += 0.10 if short_or_ambiguous else 0.16
    if ticker_in_url:
        score += 0.04

    if company_phrase_hit_title:
        score += 0.38
    elif token_hits_title >= 2:
        score += 0.30
    elif token_hits_title == 1:
        score += 0.16

    if company_phrase_hit_summary:
        score += 0.18
    elif token_hits_summary >= 2:
        score += 0.14
    elif token_hits_summary == 1:
        score += 0.07

    if int(row.get("provider_count") or 1) >= 2:
        score += 0.05

    published = pd.to_datetime(row.get("published_at"), errors="coerce", utc=True)
    if pd.notna(published):
        age_days = (now - published).total_seconds() / 86400
        if age_days <= 7:
            score += 0.10
        elif age_days <= 30:
            score += 0.05
        elif age_days > 180:
            score -= 0.18
        elif age_days > 90:
            score -= 0.09

    if legal_spam:
        score -= 0.35

    if len(title.strip()) < 20 and len(summary.strip()) < 50:
        score -= 0.10

    strong_company_evidence = company_phrase_hit_title or company_phrase_hit_summary or token_hits_title >= 2 or token_hits_summary >= 2
    any_ticker_evidence = ticker_in_title or ticker_in_summary or ticker_in_url
    any_company_evidence = strong_company_evidence or token_hits_title >= 1 or token_hits_summary >= 1

    # Guardrails for market-wide use.
    if not any_ticker_evidence and not any_company_evidence:
        score = min(score, 0.35)

    # Short symbols like GEO, SHO, CCL, A, etc. cannot become high on ticker-only evidence.
    if short_or_ambiguous and any_ticker_evidence and not any_company_evidence:
        score = min(score, 0.55)

    score = max(0.0, min(1.0, score))

    if score >= 0.72 and not legal_spam and (any_company_evidence or not short_or_ambiguous):
        label = "high"
    elif score >= 0.48 and (any_ticker_evidence or any_company_evidence):
        label = "medium"
    else:
        label = "low"

    new_row = row.to_dict()
    new_row.update({
        "company_name": company_name,
        "clean_company_name": clean_company_name,
        "cik": cik,
        "relevance_score_market": score,
        "relevance_label_market": label,
        "ticker_in_title": ticker_in_title,
        "ticker_in_summary": ticker_in_summary,
        "ticker_in_url": ticker_in_url,
        "company_phrase_hit_title": company_phrase_hit_title,
        "company_phrase_hit_summary": company_phrase_hit_summary,
        "company_token_hits_title": token_hits_title,
        "company_token_hits_summary": token_hits_summary,
        "short_or_ambiguous_ticker": short_or_ambiguous,
        "possible_legal_spam": legal_spam,
    })
    rows.append(new_row)

scored = pd.DataFrame(rows)

scored = scored.sort_values(
    ["relevance_score_market", "ticker", "published_at"],
    ascending=[False, True, False],
    na_position="last",
)

scored_csv = out_dir / "cbworker_news_sources_scored_market.csv"
scored_parquet = out_dir / "cbworker_news_sources_scored_market.parquet"

scored.to_csv(scored_csv, index=False)
scored.to_parquet(scored_parquet, index=False)

candidates = scored[
    scored["relevance_label_market"].isin(["high", "medium"]) &
    (~scored["possible_legal_spam"])
].copy()

candidates = (
    candidates.sort_values(["ticker", "relevance_score_market", "published_at"], ascending=[True, False, False])
              .groupby("ticker", group_keys=False)
              .head(25)
)

cand_csv = out_dir / "cbworker_news_candidates_market.csv"
cand_parquet = out_dir / "cbworker_news_candidates_market.parquet"

candidates.to_csv(cand_csv, index=False)
candidates.to_parquet(cand_parquet, index=False)

print(f"scored rows: {len(scored)}")
print(scored["relevance_label_market"].value_counts())
print()
print(f"candidate rows: {len(candidates)}")
print(candidates.groupby("ticker").size().sort_values(ascending=False))
print()
print(f"wrote {scored_csv}")
print(f"wrote {scored_parquet}")
print(f"wrote {cand_csv}")
print(f"wrote {cand_parquet}")
