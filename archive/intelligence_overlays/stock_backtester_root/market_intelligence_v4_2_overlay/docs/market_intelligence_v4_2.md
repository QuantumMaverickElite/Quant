# Market Intelligence v4.2

Purpose: simulate the existing strategy versus heuristic NLP versus walk-forward ML as equity curves, including bootstrap spaghetti plots.

## What changed

Added:

```text
scripts/simulate_intelligence_equity_curves.py
```

It consumes saved `*_predictions.parquet` files, so no retraining is required.

It writes:

- `portfolio_returns.csv`
- `deterministic_equity.csv`
- `bootstrap_equity_paths.csv`
- `bootstrap_summary.csv`
- `equity_simulation_summary.csv`
- `plots/deterministic_equity.png`
- `plots/bootstrap_spaghetti.png`
- `plots/ml_minus_baseline_distribution.png`

## Apply

From `~/projects/quant/stock-backtester`:

```bash
cp market_intelligence_v4_2_overlay/scripts/simulate_intelligence_equity_curves.py scripts/simulate_intelligence_equity_curves.py && cp market_intelligence_v4_2_overlay/docs/market_intelligence_v4_2.md docs/market_intelligence_v4_2.md
```

## Run Best Config Automatically

This uses `all_monte_carlo_ranked.csv` to select the best matching config for `next_5d_return` and `top_n=5`.

```bash
python -m scripts.simulate_intelligence_equity_curves --run-dir outputs/intelligence/training_runs/sec_news_massive_full_pool --return-col next_5d_return --top-n 5 --cash 10000 --iterations 5000 --block-size 1 --spaghetti-paths 150 --out-dir outputs/intelligence/training_runs/sec_news_massive_full_pool/equity_sim_top5_5d
```

## Run Explicit Winning Config

```bash
python -m scripts.simulate_intelligence_equity_curves --predictions outputs/intelligence/training_runs/sec_news_massive_full_pool/wf_logistic_train126_embargo20_min100_alpha10p0_predictions.parquet --return-col next_5d_return --top-n 5 --cash 10000 --iterations 5000 --block-size 1 --spaghetti-paths 150 --out-dir outputs/intelligence/training_runs/sec_news_massive_full_pool/equity_sim_train126_embargo20_alpha10_top5_5d
```

## Open Plots

```bash
xdg-open outputs/intelligence/training_runs/sec_news_massive_full_pool/equity_sim_top5_5d/plots/deterministic_equity.png &
xdg-open outputs/intelligence/training_runs/sec_news_massive_full_pool/equity_sim_top5_5d/plots/bootstrap_spaghetti.png &
xdg-open outputs/intelligence/training_runs/sec_news_massive_full_pool/equity_sim_top5_5d/plots/ml_minus_baseline_distribution.png &
```

## Interpretation

This is still a walk-forward test over the available historical signal dates. It is closer to a portfolio simulation than the earlier average-return Monte Carlo, but it is not yet a production backtest with execution costs, slippage, borrow constraints, or portfolio overlap controls.

For `next_5d_return`, the test steps are closest to non-overlapping 5-day holding windows.

For `next_10d_return`, be careful: if the walk-forward step is 5 days, 10-day outcomes overlap. Use it for comparison, not as a clean compounded trading ledger.
