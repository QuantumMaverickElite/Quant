#!/usr/bin/env bash
set -euo pipefail

REMOTE="${1:-}"
MODE="${2:-dry-run}"

if [ -z "$REMOTE" ]; then
  echo "usage: $0 USER@HOST [dry-run]"
  echo "example: $0 elijah@100.110.132.34 dry-run"
  exit 1
fi

if [ "$MODE" != "dry-run" ]; then
  echo "only dry-run mode is enabled for now"
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
echo "== running remote dry run =="

ssh "$REMOTE" '
cd ~/quant-worker/stock-backtester

python -m venv .venv
. .venv/bin/activate

python -m pip install --upgrade pip >/dev/null
python -m pip install pandas pyarrow >/dev/null

PYTHONPATH=src python -m py_compile scripts/run_llm_classification_batch.py

PYTHONPATH=src python scripts/run_llm_classification_batch.py \
  --events outputs/intelligence/llm_benchmark_mixed_50.parquet \
  --out outputs/intelligence/llm_event_classifications_mixed50_batch.jsonl \
  --chunk-size 2 \
  --max-chunks 2 \
  --models github_gpt41,github_deepseek_v3,github_llama33_70b,github_gpt4o \
  --dry-run
'

echo
echo "done"
