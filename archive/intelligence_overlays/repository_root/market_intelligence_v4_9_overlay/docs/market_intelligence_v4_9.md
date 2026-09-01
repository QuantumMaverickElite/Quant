# Market Intelligence v4.9 - Expanded Training and Overfit Gates

## Purpose

This overlay moves the ML sentiment allocator from policy tuning into research discipline:

- train and evaluate across multiple market periods;
- keep walk-forward/purged training with embargoes;
- validate the same candidate across independent periods;
- compare every candidate against within-date permutation nulls;
- reject candidates that look good only in one regime or one top-N slice.

The current evidence says the ML layer has signal, but the dataset is still too small and the best 2022-2023 top-10 result is not enough to promote live. This overlay is built to expand the panel before integration.

## Files

- `scripts/run_multi_period_intelligence_research.py`
  - runs `scripts.run_historical_intelligence_stress` over several historical periods;
  - supports price download, news fetch, sentiment scoring, walk-forward training, policy sweeps, and equity simulations through the existing stress runner;
  - writes `multi_period_manifest.csv`.
- `scripts/score_ml_research_gates.py`
  - combines validation summaries and permutation-test summaries;
  - scores row-level gates by period/return/top-N;
  - scores candidate-level promotion gates across periods.

## Install

From `~/projects/quant`:

```bash
unzip -o ~/Downloads/market_intelligence_v4_9_clean_overlay.zip
cp market_intelligence_v4_9_overlay/scripts/run_multi_period_intelligence_research.py stock-backtester/scripts/run_multi_period_intelligence_research.py
cp market_intelligence_v4_9_overlay/scripts/score_ml_research_gates.py stock-backtester/scripts/score_ml_research_gates.py
cp market_intelligence_v4_9_overlay/docs/market_intelligence_v4_9.md stock-backtester/docs/market_intelligence_v4_9.md
cd stock-backtester
python -m compileall -q scripts
```

## Recommended Research Run

Start with a dry run to confirm paths and commands:

```bash
python -m scripts.run_multi_period_intelligence_research \
  --dry-run \
  --download-prices \
  --fetch-news \
  --include-massive \
  --keep-going
```

Then run the expanded research job:

```bash
mkdir -p outputs/intelligence/training_runs/multi_period_ml_research
nohup python -m scripts.run_multi_period_intelligence_research \
  --signals outputs/signals/mean_reversion_latest_with_intelligence.parquet \
  --work-root outputs/intelligence/training_runs/multi_period_ml_research \
  --periods \
    2020_2021=2020-01-01:2021-12-31 \
    2022_2023=2022-01-01:2023-12-31 \
    2024_2026=2024-01-01:2026-05-28 \
  --download-prices \
  --fetch-news \
  --include-massive \
  --iterations 20000 \
  --equity-iterations 10000 \
  --train-days-list 126 252 \
  --embargo-days-list 10 20 \
  --alpha-list 3 10 30 \
  --model-types logistic \
  --min-train-rows-list 100 200 \
  --keep-going \
  > outputs/intelligence/training_runs/multi_period_ml_research/run.log 2>&1 &
```

Monitor:

```bash
tail -f outputs/intelligence/training_runs/multi_period_ml_research/run.log
cat outputs/intelligence/training_runs/multi_period_ml_research/multi_period_manifest.csv
```

## Gate Scoring

After period-level validation and permutation tests exist, score them together:

```bash
python -m scripts.score_ml_research_gates \
  --validation outputs/intelligence/training_runs/ml_policy_candidate_validation_multi/ml_policy_candidate_validation.csv \
  --permutation \
    2022_2023=outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/permutation_policy_strength20_cap010_min002/ml_policy_permutation_summary.csv \
    2025_2026=outputs/intelligence/training_runs/sec_news_massive_full_pool/permutation_policy_strength20_cap010_min002/ml_policy_permutation_summary.csv \
  --out outputs/intelligence/training_runs/ml_policy_candidate_validation_multi/ml_research_gate_scores.csv \
  --min-periods 2 \
  --max-p-value 0.05 \
  --require-positive-p05
```

Promotion rule:

- validation lift must be positive;
- validation p05 must be non-negative when `--require-positive-p05` is used;
- permutation p-value must be at or below `--max-p-value`;
- true lift must exceed the shuffled-null 95th percentile;
- the same return/top-N candidate must pass in at least `--min-periods` periods.

## Current Interpretation

The 2022-2023 top-10 policy looked strong in raw Monte Carlo, but the permutation test showed that result did not clear the shuffled-null 95th percentile. The 2025-2026 holdout also did not confirm the same 10-day top-10 policy.

That means the current ML layer should remain research-only. The next valid milestone is not stronger integration; it is a larger point-in-time panel and a candidate that passes the gate scorer across periods.
