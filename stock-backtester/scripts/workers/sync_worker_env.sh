#!/usr/bin/env bash
set -euo pipefail

REMOTE="${1:-chromebook-worker}"
LOCAL_DIR="$HOME/.config/quant"
REMOTE_DIR="~/.config/quant"

FILES=(
  "llm_github_models.env"
  "llm_gemini.env"
  "worker.env"
  "workers.conf"
)

echo "== syncing env/config files to $REMOTE =="

ssh "$REMOTE" "mkdir -p $REMOTE_DIR && chmod 700 $REMOTE_DIR"

for f in "${FILES[@]}"; do
  src="$LOCAL_DIR/$f"

  if [ -f "$src" ]; then
    echo "copying $f"
    scp "$src" "$REMOTE:$REMOTE_DIR/$f" >/dev/null
  else
    echo "skipping missing $f"
  fi
done

ssh "$REMOTE" "
chmod 600 ~/.config/quant/*.env 2>/dev/null || true
chmod 600 ~/.config/quant/workers.conf 2>/dev/null || true

echo
echo '== remote files =='
ls -lh ~/.config/quant

echo
echo '== remote variable names only =='
for f in ~/.config/quant/*.env; do
  [ -f \"\$f\" ] || continue
  echo
  echo \"== \$(basename \"\$f\") ==\"
  grep -E '^(export )?[A-Za-z_][A-Za-z0-9_]*=' \"\$f\" | sed 's/=.*$/=.../' || true
done
"

echo
echo "done"
