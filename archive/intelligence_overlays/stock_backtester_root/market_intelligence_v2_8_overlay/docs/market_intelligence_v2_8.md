# Market Intelligence v2.8

Adds a grid Monte Carlo runner for comparing:

- baseline strategy ranking: volatility/entropy/correlation/mean-reversion confidence
- NLP-adjusted ranking: baseline confidence after news/sentiment/regime/opportunity adjustment

The script runs multiple top-N portfolio sizes and return horizons in one command.

Output:

- `outputs/intelligence/strategy_nlp_monte_carlo_grid.csv`
- `outputs/intelligence/strategy_nlp_monte_carlo_raw_summary.csv`

Important limitation:

This still tests the current evaluated news slice. It is not a point-in-time historical NLP backtest until historical news snapshots are collected or purchased.
