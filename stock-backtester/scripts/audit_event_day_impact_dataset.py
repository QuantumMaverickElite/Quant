#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import pandas as pd

p = Path("outputs/intelligence/event_day_impact_dataset.parquet")
df = pd.read_parquet(p)

out_dir = Path("outputs/intelligence/audits")
out_dir.mkdir(parents=True, exist_ok=True)

print("== event day impact dataset audit ==")
print(f"rows: {len(df)}")
print(f"columns: {len(df.columns)}")
print(f"tickers: {df['ticker'].nunique()}")

print()
print("== date range ==")
print("min:", df["event_base_date"].min())
print("max:", df["event_base_date"].max())

print()
print("== rows by ticker ==")
print(df.groupby("ticker").size().sort_values(ascending=False).to_string())

print()
print("== target summary ==")
print(df["target_forward_alpha"].describe().to_string())

print()
print("== target by ticker ==")
print(
    df.groupby("ticker")["target_forward_alpha"]
    .agg(["count", "mean", "std", "min", "max"])
    .sort_values("count", ascending=False)
    .to_string()
)

print()
print("== event_count pressure ==")
print(df["event_count"].describe().to_string())

print()
print("== largest event days ==")
cols = [
    "ticker",
    "event_base_date",
    "event_count",
    "provider_count",
    "unique_title_count",
    "sentiment_mean",
    "sentiment_sum",
    "target_forward_alpha",
]
print(df[cols].sort_values("event_count", ascending=False).head(30).to_string(index=False))

print()
print("== leakage sanity checks ==")
dupes = df.duplicated(["ticker", "event_base_date"]).sum()
print(f"duplicate ticker/base-date rows: {dupes}")

bad_dates = pd.to_datetime(df["event_base_date"], errors="coerce").isna().sum()
print(f"bad event_base_date rows: {bad_dates}")

spy_rows = int((df["ticker"] == "SPY").sum())
print(f"SPY rows: {spy_rows}")

audit_path = out_dir / "event_day_impact_dataset_audit.csv"
df[cols].sort_values(["event_base_date", "ticker"]).to_csv(audit_path, index=False)
print()
print(f"wrote {audit_path}")

print()
print("Audit complete.")
