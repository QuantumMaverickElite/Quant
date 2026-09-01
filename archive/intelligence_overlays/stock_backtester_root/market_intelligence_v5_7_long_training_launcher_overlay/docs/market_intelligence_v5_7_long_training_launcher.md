# Market Intelligence v5.7 Long Training Launcher

This patch adds detached long-run launch and monitor scripts.

## Why

The previous training session was long enough that we should avoid hand-running a fragile terminal command. The launcher:

- checks required scripts and input files
- compiles Python source first
- optionally runs `cargo build --release`
- writes a reproducible `run_long_training.sh`
- launches detached with a PID and log file
- keeps outputs under one run directory

## Default Profile

`short_horizon` is the default because the current 20-30 day window is too slow for alpha.

It trains:

- target: `success_5d`
- horizons: `1, 3, 5, 10`
- return columns: `next_1d_return, next_3d_return, next_5d_return, next_10d_return`
- train windows: `63, 126, 252`
- embargo: `3, 5, 10`
- models: `logistic, ridge`
- alpha: `1, 3, 10, 30`
- Monte Carlo iterations: default `50,000`

## Launch

`python scripts/launch_long_intelligence_training.py --profile short_horizon --run-name long_v5_7_short_horizon_2022_2023 --nlp-device cpu --cargo-release`

## Monitor

`python scripts/monitor_long_intelligence_training.py --run-dir outputs/intelligence/training_runs/long_v5_7_short_horizon_2022_2023`

## Resume Behavior

The generated run uses `--skip-existing` and `--keep-going`, so if a step finishes and the process is interrupted later, rerunning the launcher with the same `--run-name` should skip existing major artifacts where the underlying scripts support it.

## Adding New Source Files

Use `--news-sources` to explicitly include RSS or other merged/scored files:

`python scripts/launch_long_intelligence_training.py --run-name long_v5_7_with_rss --news-sources data/intelligence/historical/raw/news_eval_2025_2026_merged_full_scored.jsonl data/intelligence/historical/raw/sec_eval_2025_2026.jsonl data/intelligence/historical/raw/rss_entity_search_smoke_title_filtered.jsonl`

The RSS smoke file is tiny and mostly useful for compatibility. For real RSS training value, first collect a broader date/ticker RSS panel and sentiment-score it.
