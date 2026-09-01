# Market Intelligence v4.3 - 2022-2023 Historical Stress Runner

This patch adds an unattended historical stress-test runner for the allocator + NLP/ML overlay.

The purpose is to test whether historical news/analyst sentiment improves the existing allocator, not to test sentiment by itself.

## Added

- `scripts/run_historical_intelligence_stress.py`
  - validates base allocator signal coverage for the requested period
  - builds a historical signal seed panel
  - downloads/labels forward outcomes
  - optionally fetches historical news in resumable chunks
  - merges and deduplicates source files
  - scores news with FinBERT or heuristic sentiment
  - builds point-in-time news and analyst features
  - trains walk-forward ML calibrations
  - runs heavy Monte Carlo across configs
  - summarizes ranked ML-vs-baseline results
  - writes equity curve and bootstrap spaghetti plots for the best config

- `scripts/build_historical_intelligence_panel_seed.py`
- `src/backtester/intelligence/historical_panel_builder.py`
- refreshed news fetch/merge/score helpers used by the stress runner
- refreshed Monte Carlo summary scripts with tie/non-worse metrics

## Recommended Heavy 2022-2023 Run

From `stock-backtester`:

```bash
mkdir -p outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment
nohup python -m scripts.run_historical_intelligence_stress \
  --signals outputs/signals/mean_reversion_latest_with_intelligence.parquet \
  --start 2022-01-01 \
  --end 2023-12-31 \
  --work-dir outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment \
  --download-prices \
  --fetch-news \
  --include-massive \
  --chunk-size 5 \
  --limit 100 \
  --massive-sleep-seconds 30 \
  --max-retries 8 \
  --backoff-seconds 60 \
  --score-sentiment \
  --nlp-device cpu \
  --iterations 50000 \
  --equity-iterations 50000 \
  --train-days-list 126 252 \
  --embargo-days-list 10 20 \
  --alpha-list 3 10 30 \
  --model-types logistic \
  --min-train-rows-list 100 200 \
  --top-ns 5 10 15 20 30 40 50 \
  --equity-return-col next_5d_return \
  --equity-top-n 5 \
  --keep-going \
  > outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/run.log 2>&1 &
```

Monitor it:

```bash
tail -f outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/run.log
```

## Outputs

Primary outputs:

- `outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/stress_manifest.csv`
- `outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/all_monte_carlo_ranked.csv`
- `outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/equity_spaghetti_next_5d_return_top5/equity_simulation_summary.csv`

Plots:

- `outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/equity_spaghetti_next_5d_return_top5/plots/deterministic_equity.png`
- `outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/equity_spaghetti_next_5d_return_top5/plots/bootstrap_spaghetti.png`
- `outputs/intelligence/training_runs/stress_2022_2023_ml_sentiment/equity_spaghetti_next_5d_return_top5/plots/ml_minus_baseline_distribution.png`

## Interpretation

The test compares three ranking policies over the same historical allocator candidates:

- `baseline`: existing allocator rank
- `heuristic_nlp`: existing hand-built intelligence adjustment
- `walk_forward_ml`: ML-adjusted rank trained only on prior data with an embargo

The run is meaningful only if the input signal file contains the requested historical dates. If the runner reports insufficient 2022-2023 signal coverage, rebuild the base strategy signal history first.

## Bias Controls

- Signal dates are filtered before feature construction.
- Forward labels are built after the historical seed panel.
- News features use only articles published on or before each signal date.
- Walk-forward training uses train/test splits with an embargo.
- Monte Carlo bootstraps completed walk-forward test windows.

