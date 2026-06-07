#!/usr/bin/env bash
set -euo pipefail

DATE="${1:-2026-05-27}"

RETURNS_META="${RETURNS_META:-outputs/cache/returns/h100_market_common_stock_only_v3_clipped/returns_meta.json}"
SIGNALS="${SIGNALS:-outputs/signals/mean_reversion_signals_context_adjusted.parquet}"
CONTEXT="${CONTEXT:-outputs/context/market_context_with_regime_deformation.parquet}"
TICKER_SENSITIVITY="${TICKER_SENSITIVITY:-outputs/correlation/regime_ticker_stress_sensitivity.csv}"

COMBINED_STATE="${COMBINED_STATE:-outputs/allocator/combined_market_signal_state.parquet}"
OVERLAY="${OVERLAY:-outputs/market_fabric/allocator_visual_overlay.parquet}"

BASE_DIR="outputs/market_graph_fabric_frames/combined_allocator_latest_${DATE}"
AUG_DIR="${BASE_DIR}_augmented"

python scripts/build_combined_market_signal_state.py \
  --signals "${SIGNALS}" \
  --context "${CONTEXT}" \
  --ticker-sensitivity "${TICKER_SENSITIVITY}" \
  --out "${COMBINED_STATE}" \
  --latest-out outputs/allocator/combined_market_signal_state_latest.csv

python scripts/build_market_fabric_visual_overlay_from_combined_state.py \
  --combined-state "${COMBINED_STATE}" \
  --out "${OVERLAY}" \
  --latest-out outputs/market_fabric/allocator_visual_overlay_latest.csv

python visuals/build_market_graph_frames.py \
  --returns-meta "${RETURNS_META}" \
  --signals "${SIGNALS}" \
  --context "${CONTEXT}" \
  --out-dir "${BASE_DIR}" \
  --start-date "${DATE}" \
  --end-date "${DATE}" \
  --frame-step-days 1 \
  --lookback 120 \
  --forward-days 60 \
  --max-nodes 1200 \
  --top-signal-nodes 30 \
  --extra-signal-neighborhood 150 \
  --extra-random-nodes 250 \
  --extra-volatile-nodes 250 \
  --top-k-edges 4 \
  --min-edge-corr 0.45 \
  --max-edges 5000 \
  --layout-engine cluster-ring \
  --z-mode corr_degree \
  --color-mode corr_degree \
  --use-cupy \
  --force-rebuild

python scripts/augment_market_graph_frames_with_allocator_overlay.py \
  --frames-dir "${BASE_DIR}" \
  --allocator-overlay "${OVERLAY}" \
  --out-dir "${AUG_DIR}" \
  --force

python visuals/visualize_market_graph_fabric.py \
  --frames-dir "${AUG_DIR}" \
  --visual-preset clean-points \
  --use-allocator-overlay \
  --allocator-highlight-top \
  --allocator-size-boost 5.0 \
  --ticker-labels \
  --cluster-labels \
  --node-size 2.8 \
  --edge-alpha 0.14 \
  --edge-width 0.08 \
  --edge-cyan \
  --node-size-metric none
