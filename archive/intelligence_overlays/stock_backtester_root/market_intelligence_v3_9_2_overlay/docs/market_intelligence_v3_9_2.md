# Market Intelligence v3.9.2

Purpose: fix Monte Carlo result interpretation for unchanged ML rankings.

## What changed

Monte Carlo previously reported:

```text
prob_ml_beats_baseline = mean(ml_lift > 0)
```

That is mathematically strict, but misleading when ML and baseline select the same names. A tie produced `0.0`, which looked like a loss.

The summary now also reports:

- `prob_ml_ties_baseline`
- `prob_ml_ties_heuristic`
- `prob_ml_nonworse_baseline`
- `prob_ml_nonworse_heuristic`

Use:

- `prob_ml_beats_*` for strict outperformance.
- `prob_ml_ties_*` to identify unchanged rank sets.
- `prob_ml_nonworse_*` to separate losses from ties.

## Apply

From `~/projects/quant/stock-backtester`:

```bash
cp market_intelligence_v3_9_2_overlay/scripts/monte_carlo_walk_forward_predictions.py scripts/monte_carlo_walk_forward_predictions.py && cp market_intelligence_v3_9_2_overlay/scripts/summarize_intelligence_training_run.py scripts/summarize_intelligence_training_run.py && cp market_intelligence_v3_9_2_overlay/docs/market_intelligence_v3_9_2.md docs/market_intelligence_v3_9_2.md
```

This affects future Monte Carlo files. Existing `*_monte_carlo.csv` files can be regenerated from their saved `*_predictions.parquet` files.
