# Market Intelligence v4.1

Purpose: monitor ML training progress and plot the trajectory of completed walk-forward/Monte Carlo configs.

## What changed

Added:

```text
scripts/monitor_intelligence_training.py
```

It reads a training run directory while the batch is still active and writes:

- `training_monitor_trajectory.csv`
- `ml_lift_trajectory.png`
- `top_lift_<return_col>_top<top_n>.png`

## Apply

From `~/projects/quant/stock-backtester`:

```bash
cp market_intelligence_v4_1_overlay/scripts/monitor_intelligence_training.py scripts/monitor_intelligence_training.py && cp market_intelligence_v4_1_overlay/docs/market_intelligence_v4_1.md docs/market_intelligence_v4_1.md
```

## One-Shot Snapshot

```bash
python -m scripts.monitor_intelligence_training --run-dir outputs/intelligence/training_runs/sec_news_massive_full_pool --plots-dir outputs/intelligence/training_runs/sec_news_massive_full_pool/plots --return-col next_5d_return --top-n 5
```

## Live Monitor

```bash
python -m scripts.monitor_intelligence_training --run-dir outputs/intelligence/training_runs/sec_news_massive_full_pool --plots-dir outputs/intelligence/training_runs/sec_news_massive_full_pool/plots --return-col next_5d_return --top-n 5 --watch --interval-seconds 60
```

## Outputs

```text
outputs/intelligence/training_runs/sec_news_massive_full_pool/training_monitor_trajectory.csv
outputs/intelligence/training_runs/sec_news_massive_full_pool/plots/ml_lift_trajectory.png
outputs/intelligence/training_runs/sec_news_massive_full_pool/plots/top_lift_next_5d_return_top5.png
```

## Interpretation

- `cash_ml_minus_baseline`: lift for the best row in each completed config file.
- `best_cash_ml_minus_baseline_so_far`: running best lift as configs complete.
- `prob_ml_beats_baseline`: bootstrap probability that ML beats baseline.

The plot is not a neural-network loss curve. It is the empirical trajectory of completed out-of-sample strategy tests as the grid finishes.
