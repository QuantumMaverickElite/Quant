# Market Intelligence v5.7.2 Training Launcher Price Fix

The v5.7.1 run failed at `build_outcome_labels` with:

`ValueError: Either prices_path or download=True is required.`

That means the current `build_outcome_labels.py` path needs either an explicit price file or the `--download-prices` flag.

v5.7.2 changes the launcher to pass `--download-prices` by default and preserve `--download-period 10y`.

## Relaunch

Use a fresh run name:

`python scripts/launch_long_intelligence_training.py --profile compatible_10d --run-name long_v5_7_2_compatible_10d_2022_2023 --nlp-device cpu --cargo-release`

Monitor:

`python scripts/monitor_long_intelligence_training.py --run-dir outputs/intelligence/training_runs/long_v5_7_2_compatible_10d_2022_2023`

If you already have prices cached and want to avoid network downloads:

`python scripts/launch_long_intelligence_training.py --profile compatible_10d --run-name long_v5_7_2_no_price_download --no-download-prices --nlp-device cpu --cargo-release`

Do not use `--no-download-prices` unless the underlying script has another price path available.
