# Threshold Rebalance Experiments

Threshold rebalance experiments test when the allocator should switch holdings.

Instead of rebalancing every period, the system can rebalance only when the candidate portfolio improves enough over the current portfolio.

## Concept

```text
current portfolio score
candidate portfolio score
improvement = candidate_score - current_score

if improvement >= threshold:
    rebalance
else:
    keep current holdings
```

## Main Scripts

```text
scripts/threshold_rebalance_fast_v2.py
scripts/threshold_rebalance_fast_v3.py
scripts/threshold_rebalance_matrix_engine.py
```

## Example

```bash
python scripts/threshold_rebalance_fast_v3.py \
  --runs 1000 \
  --sample-size 24 \
  --portfolio-size 8 \
  --thresholds 0.00 0.01 0.03 0.05 0.075 0.10 0.15 0.20 \
  --save-mode none \
  --workers 4 \
  --progress-every 100
```

## Deterministic Selection

The threshold rebalance scripts now use deterministic top-N selection.

Tie-break rule:

```text
1. Higher score wins.
2. If scores tie, lower ticker column index wins.
```

This fixed a real version-sensitive bug between NumPy 1.26 and NumPy 2.x.

## Interpretation

Low thresholds rebalance more often.

High thresholds rebalance less often.

Important metrics include:

```text
mean_return_pct
median_return_pct
mean_sharpe
mean_max_drawdown_pct
prob_loss_pct
prob_sharpe_below_1_pct
mean_rebalances
mean_turnover_pct
```

## Research Warning

The current universe has been small and partly hand-selected.

Threshold results should not be treated as robust until tested on broader, less biased universes.
