# Market Intelligence v5.0.2 - Empty Prediction Guard

## Purpose

The v5 smoke test proved the important plumbing:

- Massive API key works;
- SEC EDGAR source collection works;
- SEC rolling features join into the labeled panel;
- historical news features join into the labeled panel;
- the calibration dataset builds with SEC + news features.

The remaining failures were smoke-size edge cases:

- one walk-forward config produced zero predictions because the smoke panel was intentionally tiny;
- Monte Carlo then tried to run on that empty predictions file;
- equity plot generation tried to histogram degenerate/non-finite values.

v5.0.2 fixes those guardrails.

## Files

- `scripts/run_intelligence_training_batch.py`
  - skips Monte Carlo when a walk-forward predictions file has zero rows.
- `scripts/simulate_intelligence_equity_curves.py`
  - exits cleanly on zero-row predictions;
  - skips invalid histograms when the ML-minus-baseline distribution has no finite values;
  - uses safer histogram bins for tiny or degenerate simulations.

## Install

From `~/projects/quant`:

```bash
unzip -o ~/Downloads/market_intelligence_v5_0_2_clean_overlay.zip
cp market_intelligence_v5_0_2_overlay/scripts/run_intelligence_training_batch.py stock-backtester/scripts/run_intelligence_training_batch.py
cp market_intelligence_v5_0_2_overlay/scripts/simulate_intelligence_equity_curves.py stock-backtester/scripts/simulate_intelligence_equity_curves.py
cp market_intelligence_v5_0_2_overlay/docs/market_intelligence_v5_0_2.md stock-backtester/docs/market_intelligence_v5_0_2.md
cd stock-backtester
python -m compileall -q scripts/run_intelligence_training_batch.py scripts/simulate_intelligence_equity_curves.py
```

## Interpretation

Do not interpret the v5 smoke's ML performance as signal quality. It used only a small number of dates and produced three test windows for the valid config. The smoke is a plumbing check only.

The full v5 run should be launched separately in `outputs/intelligence/training_runs/multi_period_ml_research_v5`.
