#!/usr/bin/env bash
set -euo pipefail

REMOTE="${1:-chromebook-worker}"
MODE="${2:-small}"

case "$MODE" in
  small)
    MAX_HTTP_REQUESTS=40
    MAX_QUERIES=10
    LIMIT=10
    ;;
  medium)
    MAX_HTTP_REQUESTS=150
    MAX_QUERIES=25
    LIMIT=20
    ;;
  full)
    MAX_HTTP_REQUESTS=500
    MAX_QUERIES=0
    LIMIT=50
    ;;
  *)
    echo "usage: $0 [chromebook-worker] [small|medium|full]"
    exit 1
    ;;
esac

JOB_ID="$(date -u +%Y%m%dT%H%M%SZ)"
LOCAL_RESULTS="outputs/intelligence/worker_results/source_fetch_$JOB_ID"
LATEST_RESULTS="outputs/intelligence/worker_results/source_fetch_latest"

echo "== preparing worker bundle =="
scripts/workers/send_llm_worker_bundle.sh "$REMOTE" dry-run >/tmp/quant_worker_bundle_"$JOB_ID".log

echo "== running source fetch worker =="
echo "remote=$REMOTE"
echo "mode=$MODE"
echo "max_http_requests=$MAX_HTTP_REQUESTS"
echo "max_queries=$MAX_QUERIES"
echo "limit=$LIMIT"
echo "job_id=$JOB_ID"

ssh "$REMOTE" \
  "JOB_ID='$JOB_ID' MODE='$MODE' MAX_HTTP_REQUESTS='$MAX_HTTP_REQUESTS' MAX_QUERIES='$MAX_QUERIES' LIMIT='$LIMIT' bash -s" <<'REMOTE_SCRIPT' 2>&1 | python scripts/workers/redact_stream.py
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

        if [ "${val#\"}" != "$val" ] && [ "${val%\"}" != "$val" ]; then
          val="${val#\"}"
          val="${val%\"}"
        fi

        if [ "${val#\'}" != "$val" ] && [ "${val%\'}" != "$val" ]; then
          val="${val#\'}"
          val="${val%\'}"
        fi

        export "$key=$val"
        ;;
    esac
  done < "$file"
}

load_worker_env

if [ -z "${NEWSAPI_KEY:-}" ] && [ -n "${NEWS_API_KEY:-}" ]; then
  export NEWSAPI_KEY="$NEWS_API_KEY"
fi

PROVIDERS="rss_yahoo rss_google"

if [ -n "${ALPHA_VANTAGE_API_KEY:-}" ]; then
  PROVIDERS="$PROVIDERS alpha_vantage"
fi

if [ -n "${FINNHUB_API_KEY:-}" ]; then
  PROVIDERS="$PROVIDERS finnhub_news finnhub_recommendations"
fi

if [ -n "${NEWSAPI_KEY:-}" ]; then
  PROVIDERS="$PROVIDERS newsapi"
fi

if [ -n "${POLYGON_API_KEY:-}" ]; then
  PROVIDERS="$PROVIDERS polygon_news"
fi

if [ -n "${MASSIVE_API_KEY:-}" ]; then
  PROVIDERS="$PROVIDERS massive_news"
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

OUTDIR="outputs/intelligence/worker_source_jobs/$JOB_ID"
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

EXTRA_ARGS=()
if [ "$MAX_QUERIES" != "0" ]; then
  EXTRA_ARGS+=(--max-queries "$MAX_QUERIES")
fi

echo
echo "providers: $PROVIDERS"
echo "date range: $START_DATE to $END_DATE"
echo "output: $OUTDIR/source_fetch.jsonl"

PYTHONPATH=src python -m py_compile \
  scripts/fetch_historical_news_sources.py \
  src/backtester/intelligence/historical_news_collector.py \
  src/backtester/intelligence/historical_source_collector.py \
  src/backtester/intelligence/entity_resolver.py \
  src/backtester/intelligence/provider_policy.py

PYTHONPATH=src python scripts/fetch_historical_news_sources.py \
  --providers $PROVIDERS \
  --queries-file outputs/intelligence/worker_source_query_tickers.txt \
  --start "$START_DATE" \
  --end "$END_DATE" \
  --limit "$LIMIT" \
  --sleep-seconds 2 \
  --massive-sleep-seconds 3 \
  --max-retries 1 \
  --backoff-seconds 5 \
  --timeout-seconds 25 \
  --max-http-requests "$MAX_HTTP_REQUESTS" \
  "${EXTRA_ARGS[@]}" \
  --resume \
  --mark-empty-complete \
  --state-file "$OUTDIR/source_fetch.jsonl.state.csv" \
  --usage storage \
  --ignore-provider-policy \
  --allow-rss-body-only \
  --out "$OUTDIR/source_fetch.jsonl" 2>&1 | python scripts/workers/redact_stream.py

mkdir -p ~/quant-worker/jobs/$JOB_ID
cp "$OUTDIR"/source_fetch.jsonl* ~/quant-worker/jobs/$JOB_ID/ 2>/dev/null || true

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
