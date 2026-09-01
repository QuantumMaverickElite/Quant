# Market Intelligence v2.5

This patch adds Monte Carlo robustness diagnostics for the intelligence-adjusted
allocator.

## What it tests

Given one evaluated signal table with forward outcome labels, it compares:

- pre-intelligence top-N portfolio
- post-intelligence top-N portfolio
- random top-N portfolios sampled from the same evaluated universe
- bootstrap resamples of the selected pre/post portfolios

## Why this is the right current test

The current intelligence snapshot is point-in-time for the latest signal date.
That means a full historical intelligence backtest would be lookahead unless we
also have historical point-in-time news/intelligence snapshots.

This Monte Carlo test is not a replacement for that future historical backtest.
It is a robustness test for the current evaluated universe.

## Main outputs

- `bootstrap_prob_post_beats_pre`
- `bootstrap_lift_p05`
- `bootstrap_lift_p50`
- `bootstrap_lift_p95`
- `random_prob_pre_beats_random`
- `random_prob_post_beats_random`
- `bootstrap_prob_post_drawdown_better`

Use it after running `build_outcome_labels.py` on evaluated-only signals.
