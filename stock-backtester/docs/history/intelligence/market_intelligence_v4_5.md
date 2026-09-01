# Market Intelligence v4.5 - Controlled ML Policy Application

This patch adds:

- `scripts/apply_ml_policy_strength.py`

It applies a controlled ML policy adjustment to saved allocator predictions/signals:

```text
policy_confidence = baseline_confidence + clip(strength * (ml_confidence - baseline_confidence), -cap, +cap)
```

The 2022-2023 strength sweep showed the strongest robust candidate:

- return horizon: `next_10d_return`
- top N: `10`
- strength: `20`
- cap: `0.05`
- deterministic lift: about `$481` on `$10,000`
- bootstrap p05: positive
- changed windows: `5 / 40`

This is not enough to call production-safe yet, but it is enough to test as a controlled policy candidate.

## Apply Candidate Policy

```bash
python -m scripts.apply_ml_policy_strength \
  --signals outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/wf_logistic_train126_embargo10_min100_alpha10p0_predictions.parquet \
  --out outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/wf_logistic_train126_embargo10_min100_alpha10p0_policy_strength20_cap005.parquet \
  --strength 20 \
  --max-abs-delta 0.05 \
  --top-ns 5 10 15 20 30 40 50 \
  --return-cols next_5d_return next_10d_return \
  --cash 10000
```

Outputs:

- adjusted signal table with `allocator_confidence_ml_policy_adjusted`
- per-ticker enter/drop audit
- per-top-N summary

## What To Inspect

```bash
cat outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/wf_logistic_train126_embargo10_min100_alpha10p0_policy_strength20_cap005_policy_summary.csv
```

```bash
python - <<'PY'
import pandas as pd
p='outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/wf_logistic_train126_embargo10_min100_alpha10p0_policy_strength20_cap005_policy_audit.csv'
df=pd.read_csv(p)
print(df[df['top_n'].eq(10)].sort_values(['date','action']).to_string(index=False))
PY
```

The audit matters because the lift came from a small number of changed windows. We need to verify the ML is replacing clearly weaker names with defensible better names, not accidentally overfitting a few historical events.

## Next Validation

Before integrating this as the live allocator policy:

1. Repeat on 2024-2026.
2. Repeat on an expanded ticker universe.
3. Compare `strength=10 cap=0.05`, `strength=15 cap=0.05`, and `strength=20 cap=0.05`.
4. Add a production config flag rather than hard-coding the strength.
