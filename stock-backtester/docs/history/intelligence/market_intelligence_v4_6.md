# Market Intelligence v4.6 - Thresholded ML Policy Sweep

This patch extends the policy-strength tools with `--min-abs-delta`.

The 2022-2023 audit showed the ML policy worked on `top10/next_10d`, but one changed window was noisy:

- `2023-11-20`
- entrants had tiny policy deltas around `0.003`
- one entrant lost money over 10 days

The new threshold suppresses weak ML adjustments:

```text
raw delta = ml_confidence - baseline_confidence
scaled delta = strength * raw delta
capped delta = clip(scaled delta, -max_abs_delta, +max_abs_delta)
final delta = 0 if abs(capped delta) < min_abs_delta else capped delta
```

## Rerun Sweep With Thresholds

```bash
python -m scripts.sweep_ml_policy_strength \
  --predictions outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/wf_logistic_train126_embargo10_min100_alpha10p0_predictions.parquet \
  --out-dir outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/policy_strength_threshold_sweep_next10_top10 \
  --return-cols next_5d_return next_10d_return \
  --top-ns 5 10 15 20 30 40 50 \
  --strengths 5 10 15 20 \
  --max-abs-deltas 0.02 0.05 0.10 \
  --min-abs-deltas 0 0.005 0.01 0.02 \
  --cash 10000 \
  --iterations 50000 \
  --block-size 3 \
  --focus-return-col next_10d_return \
  --focus-top-n 10
```

## Apply A Thresholded Candidate

Start with:

```bash
python -m scripts.apply_ml_policy_strength \
  --signals outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/wf_logistic_train126_embargo10_min100_alpha10p0_predictions.parquet \
  --out outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/wf_logistic_train126_embargo10_min100_alpha10p0_policy_strength20_cap005_min001.parquet \
  --strength 20 \
  --max-abs-delta 0.05 \
  --min-abs-delta 0.01 \
  --top-ns 5 10 15 20 30 40 50 \
  --return-cols next_5d_return next_10d_return \
  --cash 10000
```

Then inspect:

```bash
python - <<'PY'
import pandas as pd
p='outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/wf_logistic_train126_embargo10_min100_alpha10p0_policy_strength20_cap005_min001_policy_audit.csv'
df=pd.read_csv(p)
print(df[df['top_n'].eq(10)].sort_values(['date','action']).to_string(index=False))
PY
```

## Interpretation

Good threshold:

- preserves most `next_10d top10` lift
- improves p05 or keeps it positive
- removes weak/noisy swaps
- reduces changed windows without killing valid high-confidence replacements

Bad threshold:

- removes the lift entirely
- only works by over-concentrating in one or two dates
