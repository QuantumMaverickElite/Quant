# Feature Matrix Monte Carlo

The feature matrix Monte Carlo path is the preferred fast research loop for MarketState allocator tests.

## Concept

Instead of recomputing expensive features for every Monte Carlo run, the project first builds a reusable feature matrix.

Then Monte Carlo simulations use that prebuilt matrix.

```text
build feature matrix once
    -> run many Monte Carlo simulations quickly
```

## Build Feature Matrix

```bash
python scripts/build_market_state_feature_matrix.py \
  -t SPY QQQ DIA IWM AAPL MSFT NVDA META AMZN GOOGL JPM COST WMT XOM CVX KO PG JNJ \
  --data-start 2015-01-01 \
  --bt-start 2018-01-01 \
  --bt-end 2026-01-01 \
  --rebalance M \
  --output-dir outputs/feature_matrix/market_state_2018_2026_quality
```

## Output Files

```text
market_state_features.csv
close_prices.csv
metadata.csv
```

## Run Monte Carlo

```bash
python scripts/monte_carlo_from_feature_matrix.py \
  --feature-path outputs/feature_matrix/market_state_2018_2026_quality/market_state_features.csv \
  --price-path outputs/feature_matrix/market_state_2018_2026_quality/close_prices.csv \
  --runs 100 \
  --sample-size 8 \
  --capital 10000 \
  --max-weight 0.35 \
  --output-dir outputs/monte_carlo/feature_matrix_2018_2026_quality_benchmark_max35
```

## Benchmarks

The Monte Carlo script compares against:

```text
equal-weight rebalance
equal-weight buy-and-hold
```

## Research Role

This path is useful for testing whether MarketState improves portfolio behavior across sampled universes.

Current results suggest the allocator behaves more defensively than pure equal-weight participation.
