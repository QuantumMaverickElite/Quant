#!/usr/bin/env bash
set -euo pipefail

REMOTE="${1:-}"
MODE="${2:-dry-run}"

if [ -z "$REMOTE" ]; then
  echo "usage: $0 USER@HOST [dry-run]"
  echo "example: $0 elijah@100.110.132.34 dry-run"
  exit 1
fi

if [ "$MODE" != "dry-run" ] && [ "$MODE" != "real-one" ]; then
  echo "usage: $0 USER@HOST [dry-run|real-one]"
  exit 1
fi

GIT_ROOT="$(git rev-parse --show-toplevel)"

if [ -d "$GIT_ROOT/stock-backtester" ]; then
  APP_DIR="$GIT_ROOT/stock-backtester"
else
  APP_DIR="$GIT_ROOT"
fi

cd "$APP_DIR"

BUNDLE="/tmp/quant_llm_worker_bundle.tar.gz"
REMOTE_APP="~/quant-worker/stock-backtester"

echo "== building worker bundle =="

tar -czf "$BUNDLE" \
  scripts/run_llm_classification_batch.py \
  scripts/classify_event_facts_llm.py \
  scripts/build_llm_benchmark_sample.py \
  src/backtester/__init__.py \
  src/backtester/intelligence/__init__.py \
  src/backtester/intelligence/llm_event_classifier.py \
  src/backtester/intelligence/historical_news_collector.py \
  src/backtester/intelligence/historical_source_collector.py \
  src/backtester/intelligence/entity_resolver.py \
  src/backtester/intelligence/provider_policy.py \
  scripts/fetch_historical_news_sources.py \
  outputs/intelligence/llm_benchmark_mixed_50.parquet \
  outputs/intelligence/llm_benchmark_mixed_50.csv

ls -lh "$BUNDLE"

echo
echo "== sending bundle to $REMOTE =="

ssh "$REMOTE" 'mkdir -p ~/quant-worker/inbox ~/quant-worker/stock-backtester'
scp "$BUNDLE" "$REMOTE:~/quant-worker/inbox/quant_llm_worker_bundle.tar.gz"

echo
echo "== unpacking bundle on worker =="

ssh "$REMOTE" '
rm -rf ~/quant-worker/stock-backtester
mkdir -p ~/quant-worker/stock-backtester
tar -xzf ~/quant-worker/inbox/quant_llm_worker_bundle.tar.gz -C ~/quant-worker/stock-backtester
cd ~/quant-worker/stock-backtester

# The worker bundle is intentionally minimal. Avoid importing the full
# intelligence package dependency tree from __init__.py.
: > src/backtester/intelligence/__init__.py

find . -maxdepth 4 -type f | sort
'

echo
echo "== preparing worker python env =="

ssh "$REMOTE" '
cd ~/quant-worker/stock-backtester

python -m venv .venv
. .venv/bin/activate

python -m pip install --upgrade pip >/dev/null
python -m pip install pandas pyarrow >/dev/null

PYTHONPATH=src python -m py_compile scripts/run_llm_classification_batch.py
'

if [ "$MODE" = "dry-run" ]; then
  echo
  echo "== running remote dry run =="

  ssh "$REMOTE" '
  cd ~/quant-worker/stock-backtester
  . .venv/bin/activate

  PYTHONPATH=src python scripts/run_llm_classification_batch.py \
    --events outputs/intelligence/llm_benchmark_mixed_50.parquet \
    --out outputs/intelligence/llm_event_classifications_mixed50_batch.jsonl \
    --chunk-size 2 \
    --max-chunks 2 \
    --models github_gpt41,github_deepseek_v3,github_llama33_70b,github_gpt4o \
    --dry-run
  '
fi


if [ "$MODE" = "source-rss-smoke" ]; then
  echo
  echo "== running RSS source smoke on worker =="

  JOB_ID="$(date -u +%Y%m%dT%H%M%SZ)"
  LOCAL_RESULTS="outputs/intelligence/worker_results/source_rss_smoke_$JOB_ID"

  ssh "$REMOTE" "
    cd ~/quant-worker/stock-backtester
    . .venv/bin/activate

    set -a
    [ -f ~/.config/quant/worker.env ] && . ~/.config/quant/worker.env
    set +a

    PYTHONPATH=src python -m py_compile \
      scripts/fetch_historical_news_sources.py \
      src/backtester/intelligence/historical_news_collector.py \
      src/backtester/intelligence/historical_source_collector.py \
      src/backtester/intelligence/entity_resolver.py \
      src/backtester/intelligence/provider_policy.py

    rm -rf outputs/intelligence/worker_source_smoke
    mkdir -p outputs/intelligence/worker_source_smoke

    PYTHONPATH=src python scripts/fetch_historical_news_sources.py \
      --providers rss_yahoo rss_google \
      --queries AMPH MSFT \
      --start 2026-06-01 \
      --end 2026-07-01 \
      --limit 5 \
      --sleep-seconds 2 \
      --max-http-requests 4 \
      --usage storage \
      --ignore-provider-policy \
      --allow-rss-body-only \
      --out outputs/intelligence/worker_source_smoke/rss_smoke.jsonl

    mkdir -p ~/quant-worker/jobs/$JOB_ID
    cp outputs/intelligence/worker_source_smoke/rss_smoke.jsonl* \
      ~/quant-worker/jobs/$JOB_ID/ 2>/dev/null || true
  "

  mkdir -p "$LOCAL_RESULTS"

  scp "$REMOTE:~/quant-worker/jobs/$JOB_ID/*" "$LOCAL_RESULTS/" 2>/dev/null || true

  rm -rf outputs/intelligence/worker_results/source_smoke_latest
  mkdir -p outputs/intelligence/worker_results/source_smoke_latest
  cp "$LOCAL_RESULTS"/* outputs/intelligence/worker_results/source_smoke_latest/ 2>/dev/null || true

  echo
  echo "pulled source RSS smoke to $LOCAL_RESULTS"
  echo "updated latest source smoke at outputs/intelligence/worker_results/source_smoke_latest"
fi

if [ "$MODE" = "real-one" ]; then
  echo
  echo "== seeding worker with cumulative output if available =="

  LOCAL_CUMULATIVE="outputs/intelligence/worker_results/chromebook_cumulative"

  if [ -f "$LOCAL_CUMULATIVE/llm_event_classifications_mixed50_batch.parquet" ]; then
    ssh "$REMOTE" 'mkdir -p ~/quant-worker/stock-backtester/outputs/intelligence'
    scp "$LOCAL_CUMULATIVE"/llm_event_classifications_mixed50_batch.* \
      "$REMOTE:~/quant-worker/stock-backtester/outputs/intelligence/" 2>/dev/null || true
  fi

  echo
  echo "== running one real API row on worker =="

  ssh "$REMOTE" '
  test -f ~/.config/quant/llm_github_models.env

  cd ~/quant-worker/stock-backtester
  . .venv/bin/activate

  PYTHONPATH=src python scripts/run_llm_classification_batch.py \
    --events outputs/intelligence/llm_benchmark_mixed_50.parquet \
    --out outputs/intelligence/llm_event_classifications_mixed50_batch.jsonl \
    --chunk-size 1 \
    --max-chunks 1 \
    --chunk-timeout 180 \
    --cooldown-between-chunks 300 \
    --models github_deepseek_v3

  job_id=$(date -u +%Y%m%dT%H%M%SZ)
  mkdir -p ~/quant-worker/jobs/$job_id

  cp outputs/intelligence/llm_event_classifications_mixed50_batch.* \
    ~/quant-worker/jobs/$job_id/ 2>/dev/null || true

  find ~/quant-worker/jobs -mindepth 1 -maxdepth 1 -type d -mtime +1 -exec rm -rf {} +

  echo "$job_id" > ~/quant-worker/latest_job_id
  echo "job_id=$job_id"
  '

  JOB_ID="$(ssh "$REMOTE" 'cat ~/quant-worker/latest_job_id')"
  LOCAL_RESULTS="outputs/intelligence/worker_results/chromebook_$JOB_ID"

  mkdir -p "$LOCAL_RESULTS"

  scp "$REMOTE:~/quant-worker/jobs/$JOB_ID/*" "$LOCAL_RESULTS/" 2>/dev/null || true

  LOCAL_CUMULATIVE="outputs/intelligence/worker_results/chromebook_cumulative"
  mkdir -p "$LOCAL_CUMULATIVE"

  cp "$LOCAL_RESULTS"/llm_event_classifications_mixed50_batch.* \
    "$LOCAL_CUMULATIVE"/ 2>/dev/null || true

  echo
  echo "pulled results to $LOCAL_RESULTS"
  echo "updated cumulative results at $LOCAL_CUMULATIVE"
fi

echo
echo "done"
