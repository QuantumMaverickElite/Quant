#!/usr/bin/env python3
from pathlib import Path
from urllib.request import Request, urlopen
import json
import re
import pandas as pd

out_dir = Path("data/reference")
out_dir.mkdir(parents=True, exist_ok=True)

url = "https://www.sec.gov/files/company_tickers.json"

req = Request(
    url,
    headers={
        "User-Agent": "stock-backtester universe builder elijah.alayev@gmail.com"
    },
)

with urlopen(req, timeout=30) as r:
    data = json.loads(r.read().decode("utf-8"))

def clean_name(name):
    name = str(name or "")
    name = name.lower()
    name = re.sub(r"\b(incorporated|inc|corp|corporation|co|company|ltd|limited|plc|holdings|holding|group|class a|class b|common stock)\b", " ", name)
    name = re.sub(r"[^a-z0-9 ]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name

rows = []
for _, item in data.items():
    ticker = str(item.get("ticker", "")).upper().strip()
    company_name = str(item.get("title", "")).strip()
    cik = str(item.get("cik_str", "")).zfill(10)

    if not ticker or not company_name:
        continue

    rows.append({
        "ticker": ticker,
        "company_name": company_name,
        "clean_company_name": clean_name(company_name),
        "cik": cik,
        "source": "sec_company_tickers",
    })

df = pd.DataFrame(rows)
df = df.drop_duplicates(subset=["ticker"], keep="first")
df = df.sort_values("ticker")

csv_path = out_dir / "ticker_universe_sec.csv"
parquet_path = out_dir / "ticker_universe_sec.parquet"

df.to_csv(csv_path, index=False)
df.to_parquet(parquet_path, index=False)

print(f"rows: {len(df)}")
print(f"wrote {csv_path}")
print(f"wrote {parquet_path}")
print(df.head(20).to_string(index=False))
