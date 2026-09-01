# Market Intelligence v4.4 - ML Policy Strength Sweep

This patch adds a fast post-training stress test:

- `scripts/sweep_ml_policy_strength.py`

It answers whether the ML sentiment rank adjustment is too weak by scaling the already trained ML-vs-baseline confidence delta without retraining.

## Why

The 2022-2023 stress test showed:

- mean absolute ML confidence movement around `0.002`
- only 1 changed top-10 window out of 40
- baseline and heuristic rankings identical
- small positive ML lift, but not enough to call material

That means the model either has weak signal, sparse inputs, or the allocator policy caps are too tight. This sweep tests the third case directly.

## Run

From `stock-backtester`:

```bash
python -m scripts.sweep_ml_policy_strength \
  --predictions outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/wf_logistic_train126_embargo10_min100_alpha10p0_predictions.parquet \
  --out-dir outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/policy_strength_sweep_next10_top10 \
  --return-cols next_5d_return next_10d_return \
  --top-ns 5 10 15 20 30 40 50 \
  --strengths 0.5 1 2 3 5 10 15 20 \
  --max-abs-deltas none 0.01 0.02 0.05 0.10 \
  --cash 10000 \
  --iterations 50000 \
  --block-size 3 \
  --focus-return-col next_10d_return \
  --focus-top-n 10
```

## Outputs

- `policy_strength_sweep_summary.csv`
- `plots/policy_strength_sweep_next_10d_return_top10.png`
- `plots/top_policy_strength_lifts.png`
- `best_policy_strength/best_policy_strength_summary.csv`
- `best_policy_strength/plots/policy_strength_deterministic_equity.png`
- `best_policy_strength/plots/policy_strength_bootstrap_spaghetti.png`
- `best_policy_strength/plots/policy_strength_ml_minus_baseline_distribution.png`

## Interpretation

Good sign:

- lift increases at `2x` or `3x`
- changed windows increase
- drawdown does not degrade materially
- bootstrap p05 stays near or above zero

Bad sign:

- lift only improves at extreme strengths like `15x` or `20x`
- p05 becomes meaningfully negative
- drawdown worsens
- gains come from one or two changed windows only

If the sweep works at moderate strength, integrate a configurable ML influence multiplier into the allocator. If it does not, the next fix is more source coverage and richer features, not looser allocation policy.

