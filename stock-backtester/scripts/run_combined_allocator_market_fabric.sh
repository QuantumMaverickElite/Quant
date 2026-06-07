#!/usr/bin/env bash
set -euo pipefail

START_DATE="${1:-2026-01-01}"
END_DATE="${2:-2026-05-27}"
STEP_DAYS="${3:-10}"

RETURNS_META="${RETURNS_META:-outputs/cache/returns/h100_market_common_stock_only_v3_clipped/returns_meta.json}"
SIGNALS="${SIGNALS:-outputs/signals/mean_reversion_signals_context_adjusted.parquet}"
CONTEXT="${CONTEXT:-outputs/context/market_context_with_regime_deformation.parquet}"
TICKER_SENSITIVITY="${TICKER_SENSITIVITY:-outputs/correlation/regime_ticker_stress_sensitivity.csv}"

COMBINED_STATE="${COMBINED_STATE:-outputs/allocator/combined_market_signal_state.parquet}"
OVERLAY="${OVERLAY:-outputs/market_fabric/allocator_visual_overlay.parquet}"

TAG="${START_DATE}_to_${END_DATE}_step_${STEP_DAYS}"
BASE_DIR="outputs/market_graph_fabric_frames/combined_allocator_${TAG}"
AUG_DIR="${BASE_DIR}_augmented"

echo "Building combined allocator market fabric"
echo "Start:        ${START_DATE}"
echo "End:          ${END_DATE}"
echo "Step days:    ${STEP_DAYS}"
echo "Returns meta: ${RETURNS_META}"
echo "Signals:      ${SIGNALS}"
echo "Context:      ${CONTEXT}"
echo "Output:       ${AUG_DIR}"
echo

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
  --start-date "${START_DATE}" \
  --end-date "${END_DATE}" \
  --frame-step-days "${STEP_DAYS}" \
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
