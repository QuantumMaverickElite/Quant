# Market Intelligence v4.7 - ML Policy Promotion Gate

This patch adds:

- `scripts/validate_ml_policy_candidate.py`

It validates one candidate ML policy across one or more prediction parquet files.

Current candidate from the 2022-2023 stress test:

```text
strength = 20
max_abs_delta = 0.10
min_abs_delta = 0.02
focus = next_10d_return, top_n=10
```

## Why

The 2022-2023 test is strong enough to continue, but not enough to promote directly.

The candidate must pass at least one more period before becoming a live allocator policy.

## Single-Period Validation

```bash
python -m scripts.validate_ml_policy_candidate \
  --predictions 2022_2023=outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/wf_logistic_train126_embargo10_min100_alpha10p0_predictions.parquet \
  --out-dir outputs/intelligence/training_runs/ml_policy_candidate_validation \
  --strength 20 \
  --max-abs-delta 0.10 \
  --min-abs-delta 0.02 \
  --return-cols next_5d_return next_10d_return \
  --top-ns 5 10 15 20 30 40 50 \
  --focus-return-col next_10d_return \
  --focus-top-n 10 \
  --cash 10000 \
  --iterations 50000 \
  --block-size 3
```

## Multi-Period Validation

Add more prediction files as `label=path`:

```bash
python -m scripts.validate_ml_policy_candidate \
  --predictions \
    2022_2023=outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/wf_logistic_train126_embargo10_min100_alpha10p0_predictions.parquet \
    2025_2026=outputs/intelligence/training_runs/sec_news_massive_full_pool/wf_logistic_train126_embargo20_min100_alpha10p0_predictions.parquet \
  --out-dir outputs/intelligence/training_runs/ml_policy_candidate_validation \
  --strength 20 \
  --max-abs-delta 0.10 \
  --min-abs-delta 0.02 \
  --return-cols next_5d_return next_10d_return \
  --top-ns 5 10 15 20 30 40 50 \
  --focus-return-col next_10d_return \
  --focus-top-n 10 \
  --cash 10000 \
  --iterations 50000 \
  --block-size 3
```

## Outputs

- `ml_policy_candidate_validation.csv`
- `focus_next_10d_return_top10.csv`
- `plots/policy_candidate_lift_by_period.png`

## Promotion Criteria

Do not promote if:

- only one period works
- p05 is materially negative
- drawdown gets worse
- lift comes from one lucky window
- top5 is damaged and the allocator cannot target top10 separately

Promote as experimental if:

- `next_10d/top10` works in at least two periods
- p05 is positive or near zero in both
- changed windows remain sparse but coherent
- drawdown is not worse
- policy is configurable and disabled by default
