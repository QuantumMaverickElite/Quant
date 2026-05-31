# Rebalance Frequency Tests

Rebalance frequency tests compare how often the portfolio should check for changes.

Possible frequencies include:

```text
D
W
B
3W
6W
M
Q
```

## Research Question

```text
How often should the allocator reconsider holdings?
```

More frequent rebalancing can improve responsiveness, but may increase turnover.

Less frequent rebalancing can reduce churn, but may miss regime changes.

## Artifacts

Important baselines can be compressed and stored externally.

Example archive:

```bash
tar -czf ~/quant_artifacts_to_save/rebalance_frequency_baselines_2026-05-31.tar.gz \
  outputs/research/rebalance_frequency \
  outputs/threshold_rebalance/weekly_check_sample24_port5_v1 \
  outputs/threshold_rebalance/weekly_check_sample24_port8_v1 \
  outputs/threshold_rebalance/weekly_check_sample24_port12_v1
```

## Storage Policy

Do not keep every curve folder locally forever.

Archive meaningful baselines, then delete local raw folders when disk space matters.
