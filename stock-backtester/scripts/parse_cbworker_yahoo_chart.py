#!/usr/bin/env python3
from pathlib import Path
import json
import re
import pandas as pd

root = Path.home() / "projects/quant/worker_ingest/chromebook"
raw_dir = root / "cache/yahoo_chart_raw"
out_dir = Path("outputs/worker_ingest/chromebook")
out_dir.mkdir(parents=True, exist_ok=True)

rows = []

for path in sorted(raw_dir.glob("*_yahoo_chart_*.json")):
    m = re.search(r"(?P<job_id>\d{8}T\d{6}Z_yahoo_chart)_(?P<ticker>.+)\.json$", path.name)
    if not m:
        continue

    job_id = m.group("job_id")
    ticker = m.group("ticker")

    try:
        data = json.loads(path.read_text())
        result = data["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        quote = result["indicators"]["quote"][0]
    except Exception as e:
        print(f"skip {path.name}: {e}")
        continue

    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    n = min(len(timestamps), len(opens), len(highs), len(lows), len(closes), len(volumes))

    for i in range(n):
        rows.append({
            "job_id": job_id,
            "ticker": ticker,
            "timestamp": timestamps[i],
            "date": pd.to_datetime(timestamps[i], unit="s", utc=True).date().isoformat(),
            "open": opens[i],
            "high": highs[i],
            "low": lows[i],
            "close": closes[i],
            "volume": volumes[i],
            "source_file": str(path),
        })

df = pd.DataFrame(rows)

if df.empty:
    raise SystemExit("no rows parsed")

csv_path = out_dir / "cbworker_yahoo_chart_prices.csv"
parquet_path = out_dir / "cbworker_yahoo_chart_prices.parquet"

df.to_csv(csv_path, index=False)
df.to_parquet(parquet_path, index=False)

print(f"rows: {len(df)}")
print(f"tickers: {df['ticker'].nunique()}")
print(f"date range: {df['date'].min()} -> {df['date'].max()}")
print(f"wrote {csv_path}")
print(f"wrote {parquet_path}")
