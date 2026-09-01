# Market Intelligence v5.7.1 Training Launcher Fix

The first v5.7 launcher used `short_horizon` by default. On the current repo, `build_outcome_labels` failed immediately with horizons `1 3 5 10`, which likely means the installed label builder still expects the legacy horizon set.

v5.7.1 changes the default to `compatible_10d`:

- horizons: `5, 10, 20`
- target: `success_10d`
- return columns: `next_5d_return, next_10d_return`
- train windows: `126, 252`
- embargo: `10, 20`
- models: `logistic, ridge`

It also makes long runs fail-fast by default. Use `--keep-going` only when intentionally debugging partial pipeline failures.

## Recovery

Stop the unhealthy v5.7 run:

`kill 3359263`

Apply this patch, then relaunch:

`python scripts/launch_long_intelligence_training.py --profile compatible_10d --run-name long_v5_7_1_compatible_10d_2022_2023 --nlp-device cpu --cargo-release`

Monitor:

`python scripts/monitor_long_intelligence_training.py --run-dir outputs/intelligence/training_runs/long_v5_7_1_compatible_10d_2022_2023`
