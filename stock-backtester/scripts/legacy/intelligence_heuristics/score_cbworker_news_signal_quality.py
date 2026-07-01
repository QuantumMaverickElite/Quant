#!/usr/bin/env python3
from pathlib import Path
import re
import pandas as pd

src = Path("outputs/worker_ingest/chromebook/cbworker_news_sources_scored_market.parquet")
out_dir = Path("outputs/worker_ingest/chromebook")
out_dir.mkdir(parents=True, exist_ok=True)

df = pd.read_parquet(src)

def s(x):
    if x is None or pd.isna(x):
        return ""
    return str(x)

high_signal_terms = {
    "earnings": [
        "earnings", "q1", "q2", "q3", "q4", "quarter", "revenue", "profit",
        "eps", "beat", "miss", "guidance", "margin", "cash flow", "results"
    ],
    "analyst": [
        "upgrade", "downgrade", "price target", "maintains", "initiates",
        "outperform", "underperform", "buy rating", "sell rating", "neutral rating"
    ],
    "deal_contract": [
        "contract", "partnership", "deal", "acquisition", "merger", "wins",
        "awarded", "collaboration", "expand partnership"
    ],
    "regulatory_legal_material": [
        "fda", "approval", "trial", "phase 2", "phase 3", "clinical",
        "sec filing", "investigation by", "doj", "antitrust", "customs"
    ],
    "product_strategy": [
        "launch", "roll out", "platform", "ai", "cloud", "chip", "data center",
        "defense system", "military", "robotics"
    ],
    "market_move": [
        "stock gains", "stock falls", "moved higher", "dropped", "surge",
        "tumble", "52-week high", "record run", "premarket"
    ],
}

low_signal_terms = [
    "enterprise value to",
    "price to sales forward",
    "price to book forward",
    "price to earnings forward",
    "actuals & estimates",
    "financial health",
    "profitability & balance sheet",
    "revenue breakdown",
    "top holdings list",
    "holding history",
    "marketcap, charts and fundamentals",
    "price prediction & forecast",
    "technical analysis: support, resistance",
    "shares sold by",
    "has $",
    "takes $",
]

legal_spam_terms = [
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
    "bronstein, gewirtz",
    "announces an investigation",
    "is investigating",
    "encourages stockholders",
    "encourages shareholders",
    "stockholders to learn more",
    "shareholders to connect",
]

def classify_signal(text_l):
    hits = []
    for label, terms in high_signal_terms.items():
        if any(t in text_l for t in terms):
            hits.append(label)
    return hits

quality_scores = []
quality_labels = []
signal_types = []
low_signal_flags = []
legal_spam_flags = []

for _, row in df.iterrows():
    title = s(row.get("title"))
    summary = s(row.get("summary"))
    provider = s(row.get("provider"))
    relevance = float(row.get("relevance_score_market") or 0)

    text_l = f"{title} {summary}".lower()

    low_signal = any(t in text_l for t in low_signal_terms)
    legal_spam = any(t in text_l for t in legal_spam_terms)
    signals = classify_signal(text_l)

    # Start from relevance, then adjust for actual usefulness.
    q = relevance

    if signals:
        q += 0.12

    if len(signals) >= 2:
        q += 0.08

    # Provider adjustment: Alpha has lots of auto-generated finance pages.
    if provider == "alpha_vantage_news":
        q -= 0.08
    elif provider == "finnhub_company_news":
        q += 0.04
    elif provider == "yahoo_rss":
        q += 0.03

    if low_signal:
        q -= 0.35

    if legal_spam:
        q -= 0.60

    # If it is relevant but no event/catalyst language appears, cap it.
    if not signals:
        q = min(q, 0.62)

    # Automated low-signal pages should not be high even when directly relevant.
    if low_signal:
        q = min(q, 0.45)

    if legal_spam:
        q = min(q, 0.25)

    q = max(0.0, min(1.0, q))

    if q >= 0.72:
        label = "high_signal"
    elif q >= 0.48:
        label = "medium_signal"
    else:
        label = "low_signal"

    quality_scores.append(q)
    quality_labels.append(label)
    signal_types.append(",".join(signals) if signals else "none")
    low_signal_flags.append(low_signal)
    legal_spam_flags.append(legal_spam)

df["signal_quality_score"] = quality_scores
df["signal_quality_label"] = quality_labels
df["signal_types"] = signal_types
df["low_signal_boilerplate"] = low_signal_flags
df["legal_spam_v2"] = legal_spam_flags

df = df.sort_values(
    ["signal_quality_score", "relevance_score_market", "ticker", "published_at"],
    ascending=[False, False, True, False],
    na_position="last",
)

scored_csv = out_dir / "cbworker_news_signal_quality.csv"
scored_parquet = out_dir / "cbworker_news_signal_quality.parquet"

df.to_csv(scored_csv, index=False)
df.to_parquet(scored_parquet, index=False)

candidates = df[
    df["signal_quality_label"].isin(["high_signal", "medium_signal"])
].copy()

# Keep a bounded number per ticker so big names do not dominate.
candidates = (
    candidates.sort_values(
        ["ticker", "signal_quality_score", "relevance_score_market", "published_at"],
        ascending=[True, False, False, False],
    )
    .groupby("ticker", group_keys=False)
    .head(15)
)

cand_csv = out_dir / "cbworker_news_signal_candidates.csv"
cand_parquet = out_dir / "cbworker_news_signal_candidates.parquet"

candidates.to_csv(cand_csv, index=False)
candidates.to_parquet(cand_parquet, index=False)

print(f"scored rows: {len(df)}")
print(df["signal_quality_label"].value_counts())
print()
print(f"candidate rows: {len(candidates)}")
print(candidates.groupby("ticker").size().sort_values(ascending=False))
print()
print(f"wrote {scored_csv}")
print(f"wrote {scored_parquet}")
print(f"wrote {cand_csv}")
print(f"wrote {cand_parquet}")

print()
print("top signal candidates:")
cols = ["ticker", "provider", "signal_quality_score", "signal_quality_label", "signal_types", "title"]
print(candidates[cols].head(40).to_string(index=False))
