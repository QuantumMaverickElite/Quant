#!/usr/bin/env bash
set -euo pipefail

REMOTE="${1:-chromebook-worker}"
MODE="${2:-small}"

case "$MODE" in
  small)
    MAX_QUERIES=10
    LIMIT=10
    RSS_CAP=10
    ALPHA_CAP=5
    FINNHUB_NEWS_CAP=10
    FINNHUB_REC_CAP=5
    NEWSAPI_CAP=5
    POLYGON_CAP=5
    MASSIVE_CAP=5
    ;;
  medium)
    MAX_QUERIES=25
    LIMIT=20
    RSS_CAP=20
    ALPHA_CAP=10
    FINNHUB_NEWS_CAP=25
    FINNHUB_REC_CAP=10
    NEWSAPI_CAP=20
    POLYGON_CAP=20
    MASSIVE_CAP=20
    ;;
  full)
    MAX_QUERIES=50
    LIMIT=50
    RSS_CAP=50
    ALPHA_CAP=20
    FINNHUB_NEWS_CAP=75
    FINNHUB_REC_CAP=25
    NEWSAPI_CAP=75
    POLYGON_CAP=75
    MASSIVE_CAP=75
    ;;
  *)
    echo "usage: $0 [chromebook-worker] [small|medium|full]"
    exit 1
    ;;
esac

JOB_ID="$(date -u +%Y%m%dT%H%M%SZ)"
LOCAL_RESULTS="outputs/intelligence/worker_results/source_fetch_balanced_$JOB_ID"
LATEST_RESULTS="outputs/intelligence/worker_results/source_fetch_balanced_latest"

echo "== preparing worker bundle =="
scripts/workers/send_llm_worker_bundle.sh "$REMOTE" dry-run >/tmp/quant_worker_bundle_balanced_"$JOB_ID".log

echo "== running balanced source fetch worker =="
echo "remote=$REMOTE"
echo "mode=$MODE"
echo "job_id=$JOB_ID"
echo "max_queries=$MAX_QUERIES"
echo "limit=$LIMIT"

ssh "$REMOTE" \
  "JOB_ID='$JOB_ID' MODE='$MODE' MAX_QUERIES='$MAX_QUERIES' LIMIT='$LIMIT' RSS_CAP='$RSS_CAP' ALPHA_CAP='$ALPHA_CAP' FINNHUB_NEWS_CAP='$FINNHUB_NEWS_CAP' FINNHUB_REC_CAP='$FINNHUB_REC_CAP' NEWSAPI_CAP='$NEWSAPI_CAP' POLYGON_CAP='$POLYGON_CAP' MASSIVE_CAP='$MASSIVE_CAP' bash -s" <<'REMOTE_SCRIPT' 2>&1 | python scripts/workers/redact_stream.py
set -euo pipefail

cd ~/quant-worker/stock-backtester
. .venv/bin/activate

load_worker_env() {
  local file="$HOME/.config/quant/worker.env"
  [ -f "$file" ] || return 0

  while IFS= read -r line || [ -n "$line" ]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"

    [ -z "$line" ] && continue
    case "$line" in \#*) continue ;; esac

    line="${line#export }"

    case "$line" in
      *=*)
        key="${line%%=*}"
        val="${line#*=}"

        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"

        case "$key" in
          ''|*[!A-Za-z0-9_]*|[0-9]*)
            continue
            ;;
        esac

        val="${val%\"}"
        val="${val#\"}"
        val="${val%\'}"
        val="${val#\'}"

        export "$key=$val"
        ;;
    esac
  done < "$file"
}

load_worker_env

if [ -z "${NEWSAPI_KEY:-}" ] && [ -n "${NEWS_API_KEY:-}" ]; then
  export NEWSAPI_KEY="$NEWS_API_KEY"
fi

DATES="$(python - <<'PY'
from datetime import date, timedelta
end = date.today()
start = end - timedelta(days=30)
print(start.isoformat(), end.isoformat())
PY
)"
START_DATE="${DATES% *}"
END_DATE="${DATES#* }"

OUTDIR="outputs/intelligence/worker_source_jobs_balanced/$JOB_ID"
mkdir -p "$OUTDIR"

python - <<'PY'
import pandas as pd
from pathlib import Path

inp = Path("outputs/intelligence/llm_benchmark_mixed_50.parquet")
out = Path("outputs/intelligence/worker_source_query_tickers.txt")

df = pd.read_parquet(inp)
tickers = (
    df["ticker"]
    .dropna()
    .astype(str)
    .drop_duplicates()
    .head(50)
    .tolist()
)

out.write_text("\n".join(tickers) + "\n")
print("tickers:", ", ".join(tickers))
PY

PYTHONPATH=src python -m py_compile \
  scripts/fetch_historical_news_sources.py \
  src/backtester/intelligence/historical_news_collector.py \
  src/backtester/intelligence/historical_source_collector.py \
  src/backtester/intelligence/entity_resolver.py \
  src/backtester/intelligence/provider_policy.py

run_provider() {
  provider="$1"
  cap="$2"

  out="$OUTDIR/provider_${provider}.jsonl"
  state="$OUTDIR/provider_${provider}.jsonl.state.csv"

  echo
  echo "== provider: $provider =="
  echo "cap=$cap max_queries=$MAX_QUERIES limit=$LIMIT"
  echo "out=$out"

  set +e
  PYTHONPATH=src python scripts/fetch_historical_news_sources.py \
    --providers "$provider" \
    --queries-file outputs/intelligence/worker_source_query_tickers.txt \
    --start "$START_DATE" \
    --end "$END_DATE" \
    --limit "$LIMIT" \
    --sleep-seconds 2 \
    --massive-sleep-seconds 3 \
    --max-retries 1 \
    --backoff-seconds 5 \
    --timeout-seconds 25 \
    --max-http-requests "$cap" \
    --max-queries "$MAX_QUERIES" \
    --resume \
    --mark-empty-complete \
    --state-file "$state" \
    --usage storage \
    --ignore-provider-policy \
    --allow-rss-body-only \
    --out "$out"
  status="$?"
  set -e

  echo "$provider,status=$status" >> "$OUTDIR/provider_status.csv"

  if [ "$status" -ne 0 ]; then
    echo "provider_failed=$provider status=$status"
  fi
}

run_provider rss_yahoo "$RSS_CAP"
run_provider rss_google "$RSS_CAP"

if [ -n "${ALPHA_VANTAGE_API_KEY:-}" ]; then
  run_provider alpha_vantage "$ALPHA_CAP"
else
  echo "skip alpha_vantage: missing key"
fi

if [ -n "${FINNHUB_API_KEY:-}" ]; then
  run_provider finnhub_news "$FINNHUB_NEWS_CAP"
  run_provider finnhub_recommendations "$FINNHUB_REC_CAP"
else
  echo "skip finnhub: missing key"
fi

if [ -n "${NEWSAPI_KEY:-}" ]; then
  run_provider newsapi "$NEWSAPI_CAP"
else
  echo "skip newsapi: missing key"
fi

if [ -n "${POLYGON_API_KEY:-}" ]; then
  run_provider polygon_news "$POLYGON_CAP"
else
  echo "skip polygon: missing key"
fi

if [ -n "${MASSIVE_API_KEY:-}" ]; then
  run_provider massive_news "$MASSIVE_CAP"
else
  echo "skip massive: missing key"
fi

python - <<'PY'
from pathlib import Path
import json

outdir = Path("outputs/intelligence/worker_source_jobs_balanced") / Path(__import__("os").environ["JOB_ID"])
merged = outdir / "source_fetch_balanced.jsonl"
summary = outdir / "provider_summary.txt"

files = sorted(outdir.glob("provider_*.jsonl"))
rows = 0
provider_counts = {}

with merged.open("w") as dst:
    for p in files:
        if p.name.endswith(".state.csv"):
            continue

        for line in p.read_text(errors="ignore").splitlines():
            if not line.strip():
                continue

            dst.write(line + "\n")
            rows += 1

            try:
                rec = json.loads(line)
                provider = rec.get("provider", p.stem.replace("provider_", ""))
            except Exception:
                provider = p.stem.replace("provider_", "")

            provider_counts[provider] = provider_counts.get(provider, 0) + 1

with summary.open("w") as f:
    f.write(f"rows={rows}\n")
    for provider, count in sorted(provider_counts.items()):
        f.write(f"{provider}={count}\n")

print()
print("== merged ==")
print("rows:", rows)
for provider, count in sorted(provider_counts.items()):
    print(f"{provider}: {count}")
PY

mkdir -p ~/quant-worker/jobs/$JOB_ID
cp "$OUTDIR"/source_fetch_balanced.jsonl* ~/quant-worker/jobs/$JOB_ID/ 2>/dev/null || true
cp "$OUTDIR"/provider_summary.txt ~/quant-worker/jobs/$JOB_ID/ 2>/dev/null || true
cp "$OUTDIR"/provider_status.csv ~/quant-worker/jobs/$JOB_ID/ 2>/dev/null || true

echo
echo "job_id=$JOB_ID"
echo "saved remote job artifacts: ~/quant-worker/jobs/$JOB_ID"
REMOTE_SCRIPT

mkdir -p "$LOCAL_RESULTS"

scp "$REMOTE:~/quant-worker/jobs/$JOB_ID/*" "$LOCAL_RESULTS/" 2>/dev/null || true

rm -rf "$LATEST_RESULTS"
mkdir -p "$LATEST_RESULTS"
cp "$LOCAL_RESULTS"/* "$LATEST_RESULTS"/ 2>/dev/null || true

echo
echo "pulled results to $LOCAL_RESULTS"
echo "updated latest results at $LATEST_RESULTS"
echo "done"
