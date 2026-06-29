# Market Intelligence v4.0

Purpose: run the remaining multi-source news fetch, scoring, ML training, Monte Carlo, and summary unattended.

## What changed

Added:

```text
scripts/run_pool_intelligence_training.py
```

It runs:

1. Remaining Massive ticker chunks.
2. Finnhub + Massive merge/dedupe.
3. FinBERT scoring for the merged full source.
4. Fast walk-forward ML grid.
5. Monte Carlo summaries.
6. Final ranked summary.

The runner writes:

```text
outputs/intelligence/training_runs/sec_news_massive_full_pool/pool_manifest.csv
outputs/intelligence/training_runs/sec_news_massive_full_pool/all_monte_carlo_ranked.csv
```

## Apply

From `~/projects/quant/stock-backtester`:

```bash
cp market_intelligence_v4_0_overlay/scripts/run_pool_intelligence_training.py scripts/run_pool_intelligence_training.py && cp market_intelligence_v4_0_overlay/docs/market_intelligence_v4_0.md docs/market_intelligence_v4_0.md
```

## Run While Away

Use this if offsets `0`, `5`, and `10` are already fetched:

```bash
mkdir -p outputs/intelligence/training_runs/sec_news_massive_full_pool
nohup python -m scripts.run_pool_intelligence_training --massive-offsets 15 20 25 30 35 40 45 --work-dir outputs/intelligence/training_runs/sec_news_massive_full_pool --iterations 5000 --keep-going > outputs/intelligence/training_runs/sec_news_massive_full_pool/run.log 2>&1 &
```

Monitor:

```bash
tail -f outputs/intelligence/training_runs/sec_news_massive_full_pool/run.log
```

Check process:

```bash
pgrep -af run_pool_intelligence_training
```

Check stage manifest:

```bash
column -s, -t outputs/intelligence/training_runs/sec_news_massive_full_pool/pool_manifest.csv | tail -40
```

When done:

```bash
python -m scripts.summarize_intelligence_training_run --run-dir outputs/intelligence/training_runs/sec_news_massive_full_pool --out outputs/intelligence/training_runs/sec_news_massive_full_pool/all_monte_carlo_ranked.csv
```

## Notes

- The default grid is intentionally fast:
  - `train_days`: 90, 126
  - `embargo_days`: 10, 20
  - `alpha`: 3, 10
  - `model_type`: logistic
  - `iterations`: 5000
- Use the fast run to decide whether the full-source data improves the signal.
- Run a deeper grid only after the fast run shows stable lift.
