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

if [ "$MODE" = "real-one" ]; then
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

  echo
  echo "pulled results to $LOCAL_RESULTS"
fi

echo
echo "done"
