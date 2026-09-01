# Market Intelligence v4.8 - Overfit Controls And More Training

This patch adds:

- `scripts/permutation_test_ml_policy.py`

The current ML sentiment work is promising but undertrained. The correct interpretation is:

- 2022-2023 showed a strong `next_10d/top10` result.
- 2025-2026 did not confirm the same horizon.
- Therefore a fixed global policy is not ready.
- We need more years, more tickers, more regimes, and stronger overfit controls.

## Core Rule

Do not integrate a policy because it works on one period.

The ML layer must pass:

1. walk-forward training with embargo
2. out-of-period validation
3. ticker/generalization validation
4. permutation/null tests
5. promotion gates by horizon and top-N

## Permutation Test

The permutation test keeps each date's ML-score distribution but shuffles ML scores across tickers inside that date.

This answers:

> Is the trained ML ranking better than random ML-like perturbations?

Run for the strong 2022-2023 candidate:

```bash
python -m scripts.permutation_test_ml_policy \
  --predictions outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/wf_logistic_train126_embargo10_min100_alpha10p0_predictions.parquet \
  --out-dir outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/permutation_policy_strength20_cap010_min002 \
  --strength 20 \
  --max-abs-delta 0.10 \
  --min-abs-delta 0.02 \
  --return-cols next_5d_return next_10d_return \
  --top-ns 5 10 15 20 30 40 50 \
  --permutations 1000 \
  --cash 10000
```

Run for the 2025-2026 comparable file:

```bash
python -m scripts.permutation_test_ml_policy \
  --predictions outputs/intelligence/training_runs/sec_news_massive_full_pool/wf_logistic_train126_embargo20_min100_alpha10p0_predictions.parquet \
  --out-dir outputs/intelligence/training_runs/sec_news_massive_full_pool/permutation_policy_strength20_cap010_min002 \
  --strength 20 \
  --max-abs-delta 0.10 \
  --min-abs-delta 0.02 \
  --return-cols next_5d_return next_10d_return \
  --top-ns 5 10 15 20 30 40 50 \
  --permutations 1000 \
  --cash 10000
```

Good sign:

- true lift is above shuffled-null p95
- permutation p-value is small
- same horizon/top-N works in multiple periods

Bad sign:

- true lift is inside the shuffled-null distribution
- p-value is large
- only one period works

## Expanded Training Plan

Build a larger panel before integration:

```text
Period A: 2020-2021
Period B: 2022-2023
Period C: 2024-2026
```

Recommended validation protocol:

- Train on A, validate on B.
- Train on A+B, validate on C.
- Train on B, validate on C.
- Train on A+C, validate on B only for research, not final promotion.
- Do not tune the final policy on the holdout.

## Anti-Memorization Requirements

Use these controls before live integration:

- purged walk-forward splits
- embargo at least equal to the target horizon
- regularization grid, but choose by holdout stability, not best in-sample lift
- source/date/ticker coverage reports
- permutation tests
- label-shuffle test for calibration models
- no feature leakage from future news, revised analyst data, or post-outcome filings
- promotion requires multiple independent periods

## Current Decision

The current policy is research-only:

```text
strength=20
max_abs_delta=0.10
min_abs_delta=0.02
```

It is not a production allocator policy yet.
