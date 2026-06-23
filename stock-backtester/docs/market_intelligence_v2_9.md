# Market Intelligence v2.9

Adds first-pass ML-calibrated intelligence scoring.

New pieces:

- `src/backtester/intelligence/calibrated_adjustment.py`
- `scripts/apply_calibrated_intelligence.py`
- `scripts/compare_allocator_rankings.py`

Purpose:

Compare three allocator rankings on the same evaluated candidate set:

- baseline: original volatility/entropy/correlation/mean-reversion allocator confidence
- heuristic NLP: current deterministic intelligence/risk/opportunity adjustment
- ML NLP: bounded calibration from the fitted ridge/logistic weights

Important limitation:

This is still a diagnostic ML layer trained on the current 73-row evaluated slice. It should not replace the heuristic allocator until we have point-in-time historical news/event training data.
