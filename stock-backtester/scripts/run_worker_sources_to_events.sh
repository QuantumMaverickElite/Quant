#!/usr/bin/env bash
set -euo pipefail

INPUT="${1:-outputs/intelligence/worker_results/source_fetch_balanced_latest/source_fetch_balanced.jsonl}"
OUTDIR="${2:-outputs/intelligence/worker_results/source_fetch_balanced_latest}"

NORMALIZED="$OUTDIR/source_fetch_balanced_normalized.parquet"
EVENTS="$OUTDIR/event_fact_table_balanced.parquet"

PYTHONPATH=src python scripts/normalize_worker_sources.py \
  --input "$INPUT" \
  --out "$NORMALIZED"

PYTHONPATH=src python scripts/build_event_fact_table.py \
  --news "$NORMALIZED" \
  --out "$EVENTS"

python - <<PY
import pandas as pd
from pathlib import Path

events = Path("$EVENTS")
df = pd.read_parquet(events)

print()
print("event table:", events)
print("rows:", len(df))
print("tickers:", df["ticker"].nunique() if "ticker" in df.columns else "n/a")
print("providers:", ", ".join(sorted(df["provider"].dropna().unique())) if "provider" in df.columns else "n/a")
PY
