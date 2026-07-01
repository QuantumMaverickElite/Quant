#!/usr/bin/env python3
from pathlib import Path
import re
import pandas as pd

src = Path("outputs/worker_ingest/chromebook/cbworker_news_sources.parquet")
out_dir = Path("outputs/worker_ingest/chromebook")
out_dir.mkdir(parents=True, exist_ok=True)

df = pd.read_parquet(src)

def safe_str(x):
    if x is None or pd.isna(x):
        return ""
    return str(x)

provider_prior = {
    "finnhub_company_news": 0.75,
    "yahoo_rss": 0.65,
    "newsapi_everything": 0.55,
    "alpha_vantage_news": 0.45,
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

scores = []
labels = []
ticker_in_title = []
ticker_in_summary = []
ticker_in_url = []
spam_flags = []

for _, row in df.iterrows():
    ticker = safe_str(row.get("ticker")).upper()
    title = safe_str(row.get("title"))
    summary = safe_str(row.get("summary"))
    url = safe_str(row.get("url"))
    provider = safe_str(row.get("provider"))

    title_u = title.upper()
    summary_u = summary.upper()
    url_u = url.upper()

    # Ticker as a rough standalone token. Good enough for v1.
    pat = re.compile(rf"(?<![A-Z0-9]){re.escape(ticker)}(?![A-Z0-9])")

    has_title = bool(pat.search(title_u))
    has_summary = bool(pat.search(summary_u))
    has_url = ticker in url_u

    text_l = f"{title} {summary}".lower()
    is_spam = any(term in text_l for term in spam_terms)

    score = provider_prior.get(provider, 0.50)

    if has_title:
        score += 0.25
    if has_summary:
        score += 0.15
    if has_url:
        score += 0.05
    if is_spam:
        score -= 0.35

    # Small penalty for very thin articles.
    if len(title.strip()) < 20 and len(summary.strip()) < 50:
        score -= 0.10

    score = max(0.0, min(1.0, score))

    if score >= 0.75:
        label = "high"
    elif score >= 0.50:
        label = "medium"
    else:
        label = "low"

    scores.append(score)
    labels.append(label)
    ticker_in_title.append(has_title)
    ticker_in_summary.append(has_summary)
    ticker_in_url.append(has_url)
    spam_flags.append(is_spam)

df["relevance_score"] = scores
df["relevance_label"] = labels
df["ticker_in_title"] = ticker_in_title
df["ticker_in_summary"] = ticker_in_summary
df["ticker_in_url"] = ticker_in_url
df["possible_legal_spam"] = spam_flags

df = df.sort_values(
    ["relevance_score", "ticker", "published_at"],
    ascending=[False, True, False],
    na_position="last",
)

csv_path = out_dir / "cbworker_news_sources_scored.csv"
parquet_path = out_dir / "cbworker_news_sources_scored.parquet"

df.to_csv(csv_path, index=False)
df.to_parquet(parquet_path, index=False)

print(f"rows: {len(df)}")
print(df["relevance_label"].value_counts())
print(f"wrote {csv_path}")
print(f"wrote {parquet_path}")

print()
print("top examples:")
cols = ["ticker", "provider", "relevance_score", "relevance_label", "possible_legal_spam", "title"]
print(df[cols].head(25).to_string(index=False))
