#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import pandas as pd

p = Path("outputs/intelligence/event_impact_dataset.parquet")
df = pd.read_parquet(p)

out_dir = Path("outputs/intelligence/audits")
out_dir.mkdir(parents=True, exist_ok=True)

print("== event impact dataset audit ==")
print(f"rows: {len(df)}")
print(f"columns: {len(df.columns)}")
print(f"tickers: {df['ticker'].nunique()}")
print(f"trainable rows: {int(df['is_trainable'].sum())}")

print()
print("== trainable by ticker ==")
train = df[df["is_trainable"]].copy()
print(train.groupby("ticker").size().sort_values(ascending=False).to_string())

print()
print("== target_forward_alpha summary by ticker ==")
print(
    train.groupby("ticker")["target_forward_alpha"]
    .agg(["count", "mean", "std", "min", "max"])
    .sort_values("count", ascending=False)
    .to_string()
)

print()
print("== target_forward_alpha by provider ==")
print(
    train.groupby("provider")["target_forward_alpha"]
    .agg(["count", "mean", "std", "min", "max"])
    .sort_values("count", ascending=False)
    .to_string()
)

print()
print("== event type target means ==")
event_cols = [
    c for c in df.columns
    if c.startswith("event_type_") and not c.endswith("_count")
]

rows = []
for c in event_cols:
    g = train[train[c] == 1]
    rows.append({
        "event_type": c,
        "count": len(g),
        "mean_alpha_5d": g["target_forward_alpha"].mean(),
        "positive_rate": g["target_positive_alpha"].mean(),
    })

event_summary = pd.DataFrame(rows).sort_values("count", ascending=False)
print(event_summary.to_string(index=False))

print()
print("== duplicate pressure: ticker/base-date groups ==")

base_col = "event_base_date_5d"
if base_col not in df.columns:
    base_col = "event_base_date_1d"

train["event_base_date_group"] = pd.to_datetime(train[base_col], errors="coerce").dt.date.astype(str)
group_cols = ["ticker", "event_base_date_group"]

grp = (
    train.groupby(group_cols)
    .agg(
        article_rows=("event_id", "count"),
        unique_titles=("title", "nunique"),
        target_forward_alpha=("target_forward_alpha", "first"),
    )
    .reset_index()
    .sort_values("article_rows", ascending=False)
)

print(grp.head(30).to_string(index=False))

print()
print("duplicate pressure stats:")
print(grp["article_rows"].describe().to_string())

audit_path = out_dir / "event_impact_duplicate_groups.csv"
grp.to_csv(audit_path, index=False)
print()
print(f"wrote {audit_path}")

print()
print("== leakage sanity checks ==")

if "event_time" in train.columns and base_col in train.columns:
    event_time = pd.to_datetime(train["event_time"], errors="coerce", utc=True)
    base_date = pd.to_datetime(train[base_col], errors="coerce", utc=True)
    bad = train[base_date < event_time.dt.normalize()]
    print(f"base date before normalized event date: {len(bad)}")

if "event_after_market_close" in train.columns and "label_candidate_date" in train.columns:
    after = train[train["event_after_market_close"].astype(bool)]
    same_candidate = after[
        pd.to_datetime(after["label_candidate_date"], errors="coerce").dt.date
        ==
        pd.to_datetime(after["event_time"], errors="coerce", utc=True)
          .dt.tz_convert("America/New_York")
          .dt.date
    ]
    print(f"after-close rows whose candidate date stayed same local date: {len(same_candidate)}")

print()
print("Audit complete. Do not train allocator-impacting model until duplicate pressure is handled.")
