# Stock Backtester — Modular Quant Research Framework

A modular Python backtesting and research framework for testing trading strategies, volatility regimes, entropy-based market states, routing logic, allocation rules, and strategy overlays.

The project started as a simple stock backtester, but has grown into a research system for comparing strategy behavior across tickers, market regimes, sampled universes, and experimental allocation pipelines.

The current architecture supports:

- Regime-based equity strategies
- Dividend/event-driven strategies
- GARCH-style volatility analytics
- Fast volatility analytics for large-scale research loops
- Return entropy and directional entropy analytics
- Volatility and entropy decision layers
- MarketState construction
- MarketState-driven paper trade plans
- MarketState portfolio backtests
- Feature-matrix based Monte Carlo simulations
- Equal-weight rebalance and buy-and-hold benchmarks
- Strategy scorecards and research comparison reports
- Simplified options overlay experiments
- Conditional options-overlay gating by ticker
- Isolated experiment output folders

Generated outputs are ignored by Git. The repository is meant to store source code, scripts, documentation, and reproducible research tools, not large backtest artifacts.

---

## Core Idea

The project is built around a research loop:

```text
strategy idea
    -> backtest
    -> isolated experiment output
    -> scorecard
    -> benchmark comparison
    -> Monte Carlo validation
    -> decision: keep, modify, or reject
```

Instead of treating every backtest as a one-off script, this framework separates the system into:

- data loading
- analytics / feature generation
- strategy signal generation
- decision / routing logic
- market-state construction
- allocation simulation
- execution / backtest engines
- risk and overlay logic
- research evaluation scripts

The long-term goal is to evolve toward a modular quant engine:

```text
strategies -> orthogonalization -> allocator -> risk -> execution
```

The current research focus is the allocator layer.

---

## Current Architecture

At a high level, the system is moving toward this structure:

```text
price data
    -> volatility features
    -> entropy features
    -> decision layers
    -> MarketState
    -> feature matrix
    -> allocator simulation
    -> Monte Carlo + benchmarks
```

The current allocator research pipeline is:

```text
price data
    -> fast volatility / GARCH volatility
    -> return entropy + directional entropy
    -> volatility decision
    -> entropy decision
    -> MarketState
    -> adjusted score
    -> portfolio weights
    -> equity curve
    -> benchmark comparison
```

---

## Project Structure

```text
stock-backtester/
├── src/backtester/
│   ├── cli.py
│   ├── data.py
│   ├── metrics.py
│   ├── plot.py
│   ├── universes.py
│   │
│   ├── analytics/
│   │   ├── entropy.py
│   │   ├── fast_volatility.py
│   │   ├── volatility.py
│   │   ├── volatility_state.py
│   │   └── options_data.py
│   │
│   ├── decision/
│   │   ├── entropy_decision.py
│   │   ├── market_state.py
│   │   ├── regime_router.py
│   │   ├── position_sizing.py
│   │   └── volatility_decision.py
│   │
│   ├── engines/
│   │   ├── position_engine.py
│   │   ├── event_engine.py
│   │   └── options_overlay_engine.py
│   │
│   ├── strategies/
│   │   ├── position_strategies.py
│   │   ├── event_strategies.py
│   │   ├── options_strategies.py
│   │   ├── options_engine.py
│   │   └── volatility_strategy.py
│   │
│   ├── models/
│   │   └── trade_result.py
│   │
│   ├── utils/
│   │   ├── output.py
│   │   └── helpers.py
│   │
│   └── visuals/
│       └── garch_state.py
│
├── scripts/
│   ├── backtest_market_state_portfolio.py
│   ├── build_market_state_feature_matrix.py
│   ├── monte_carlo_from_feature_matrix.py
│   ├── monte_carlo_market_state.py
│   ├── scan_market_state.py
│   ├── test_market_state_trades.py
│   ├── strategy_scorecard.py
│   ├── compare_equity_layers.py
│   ├── run_regime_basket.py
│   ├── summarize_regime_basket.py
│   ├── compare_regime_by_year.py
│   ├── compare_regime_runs.py
│   ├── backtest_options_overlay.py
│   └── test_*.py
│
├── docs/
│   └── market_state_engine.md
│
├── archive/
│   └── old_backtests/          # ignored; local historical outputs
│
├── outputs/                    # ignored; generated experiment outputs
├── results/                    # ignored; old generated plots
├── assets/                     # curated documentation assets only
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Running the Project

Activate the environment:

```bash
source .venv/bin/activate
```

If needed, install the package in editable mode:

```bash
pip install -e .
```

Then check the CLI:

```bash
python -m backtester.cli --help
```

---

## Core Package

### `src/backtester/cli.py`

Main command-line entry point.

It supports:

- regime strategy backtests
- dividend/event strategy backtests
- GARCH regime routing
- options overlay experiments
- ticker-gated options overlays
- custom output roots for isolated experiments

Important CLI flags:

```bash
--strategy regime
--strategy dividend
--use-regime-router
--use-options-overlay
--options-overlay-tickers NVDA TSLA
--output-root outputs/experiments/<experiment_name>
```

---

### `src/backtester/data.py`

Data loading layer.

Currently handles price retrieval and formatting for the rest of the system.

---

### `src/backtester/analytics/`

Market analytics and feature generation.

Key files:

- `volatility.py`: computes GARCH-style volatility metrics.
- `fast_volatility.py`: computes fast realized-volatility style metrics for scalable research.
- `volatility_state.py`: helpers for classifying volatility states.
- `entropy.py`: computes return entropy and directional entropy.
- `options_data.py`: options-related data helpers and experimental utilities.

---

### `src/backtester/decision/`

Decision logic and routing layer.

Key files:

- `volatility_decision.py`: converts volatility metrics into risk multipliers, strategy preferences, options permissions, and equity permissions.
- `entropy_decision.py`: converts entropy metrics into signal-trust decisions.
- `market_state.py`: combines volatility and entropy into a single allocator-facing MarketState object.
- `regime_router.py`: converts volatility state into routing decisions.
- `position_sizing.py`: applies regime-aware risk scaling to equity exposure.

This layer is where market-state information starts affecting strategy behavior.

---

### `src/backtester/engines/`

Backtest execution engines.

Key files:

- `position_engine.py`: core continuous-position backtest engine.
- `event_engine.py`: event-driven trade engine, currently used for dividend capture tests.
- `options_overlay_engine.py`: simplified options overlay engine for straddle/strangle-style return experiments.

---

### `src/backtester/strategies/`

Strategy signal logic.

Key files:

- `position_strategies.py`: regime strategy logic using momentum, streaks, crash detection, and leverage behavior.
- `event_strategies.py`: event-driven strategy helper logic.
- `options_strategies.py`: options strategy experiments.
- `volatility_strategy.py`: volatility strategy experiments.

---

### `src/backtester/utils/`

Shared utilities.

Key files:

- `output.py`: creates organized output directories and supports custom experiment roots through `--output-root`.

---

### `src/backtester/visuals/`

Visualization experiments.

Key files:

- `garch_state.py`: interactive and recorded GARCH volatility surface visualizer.

Generated visual recordings should not be committed to Git.

---

## MarketState System

The MarketState layer combines volatility and entropy into a single allocator-facing object.

The core formula is:

```text
combined_multiplier = risk_multiplier * signal_trust_multiplier
```

Where:

- `risk_multiplier` comes from the volatility decision layer.
- `signal_trust_multiplier` comes from the entropy decision layer.
- `combined_multiplier` scales the raw strategy score.
- `allow_new_equity_positions` can block new equity entries.
- `allow_options` can permit options-style logic in high-risk states.
- `capital_posture` describes the allocator stance.

Common capital postures include:

```text
NORMAL
CAUTIOUS
DEFENSIVE
CAPITAL_PRESERVATION
RESTRICTED
```

This lets the allocator respond to market conditions without hardcoding every rule directly into the trading strategy.

---

## Entropy Engine

The entropy engine measures uncertainty in returns.

It currently includes two major concepts:

```text
Return entropy:
How dispersed or abnormal return magnitudes are.

Directional entropy:
How choppy or random the up/down sequence is.
```

The entropy system produces regimes such as:

```text
LOW
NORMAL
HIGH
EXTREME
```

It also combines return entropy and directional entropy into states such as:

```text
RETURN_NORMAL_DIRECTION_NORMAL
RETURN_HIGH_DIRECTION_LOW
RETURN_EXTREME_DIRECTION_NORMAL
RETURN_HIGH_DIRECTION_EXTREME
```

The entropy decision layer then produces:

```text
signal_trust_multiplier
allow_new_signals
entropy_state_description
reason
```

The allocator uses `signal_trust_multiplier` to decide how much to trust raw momentum or strategy scores.

---

## Volatility Engines

The project currently uses two volatility concepts.

### GARCH Volatility

GARCH volatility is model-based. It attempts to estimate conditional volatility using recent shocks and recent volatility behavior.

It is useful for:

- deeper volatility analysis
- regime validation
- studying volatility clustering
- smaller-universe research

But it is slower and can be fragile in large Monte Carlo loops because it requires repeated model fitting.

### Fast Volatility

Fast volatility is a rolling-statistics proxy.

It uses realized volatility, rolling z-scores, volatility percentiles, and spike flags.

It is useful for:

- broad universe scans
- feature matrix construction
- fast Monte Carlo simulations
- future CUDA/CuPy acceleration

The current research loop uses fast volatility for scalable allocator testing and keeps GARCH available as a deeper validation tool.

---

## MarketState Research Scripts

### `scripts/scan_market_state.py`

Scans tickers and prints their current volatility regime, entropy regime, combined multiplier, permissions, capital posture, and preferred strategy.

Example:

```bash
python scripts/scan_market_state.py -t SPY QQQ NVDA JPM XOM
```

This is useful as a pre-allocator dashboard.

---

### `scripts/test_market_state_trades.py`

Generates a simple paper trade plan using:

```text
raw momentum score * MarketState combined multiplier
```

The script produces:

- raw score
- adjusted score
- target weight
- dollar allocation
- share quantity
- BUY / SKIP / BLOCK decision

Example:

```bash
python scripts/test_market_state_trades.py \
  -t META NVDA TSLA MSFT ORCL OKLO JPM COST WMT BRK-B \
  --capital 10000
```

This is not broker execution. It is a research trade plan.

---

### `scripts/backtest_market_state_portfolio.py`

Runs a historical portfolio backtest using the MarketState allocator.

The script:

1. Downloads price data.
2. Computes market state through time.
3. Computes simple momentum scores.
4. Scales scores by MarketState.
5. Assigns weights.
6. Simulates the portfolio equity curve.

Example:

```bash
python scripts/backtest_market_state_portfolio.py \
  -t META NVDA TSLA MSFT ORCL OKLO JPM COST WMT BRK-B \
  --bt-start 2025-01-01 \
  --bt-end 2026-01-01 \
  --capital 10000 \
  --rebalance M
```

---

### `scripts/build_market_state_feature_matrix.py`

Builds a reusable feature matrix for fast simulation.

This separates expensive feature generation from repeated Monte Carlo simulation.

The output feature matrix contains rows like:

```text
date
asof_date
ticker
close
raw_score
adjusted_score
vol_regime
return_entropy_regime
direction_entropy_regime
entropy_state
risk_multiplier
signal_trust_multiplier
combined_multiplier
allow_new_equity_positions
allow_options
capital_posture
preferred_strategy
```

Example:

```bash
python scripts/build_market_state_feature_matrix.py \
  -t SPY QQQ DIA IWM AAPL MSFT NVDA META AMZN GOOGL JPM COST WMT XOM CVX KO PG JNJ \
  --data-start 2015-01-01 \
  --bt-start 2018-01-01 \
  --bt-end 2026-01-01 \
  --rebalance M \
  --output-dir outputs/feature_matrix/market_state_2018_2026_quality
```

This writes:

```text
market_state_features.csv
close_prices.csv
metadata.csv
```

---

### `scripts/monte_carlo_from_feature_matrix.py`

Runs fast Monte Carlo simulations from a prebuilt feature matrix.

This script randomly samples ticker baskets, simulates MarketState allocation, and compares the result against:

```text
equal-weight monthly rebalance
equal-weight buy-and-hold
```

It produces:

- Monte Carlo trials
- distribution summaries
- benchmark comparison summaries
- risk stats
- equity curve data
- strategy spaghetti plots
- benchmark spaghetti plots
- median strategy-vs-benchmark chart

Example:

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

Useful output chart:

```text
outputs/monte_carlo/<experiment>/plots/median_strategy_vs_benchmarks.png
```

---

### `scripts/monte_carlo_market_state.py`

Older Monte Carlo runner that directly recomputes backtests across random universes.

This is useful for validation, but slower than the feature-matrix version because it recomputes expensive features inside the simulation loop.

The preferred fast research path is now:

```text
build_market_state_feature_matrix.py
    -> monte_carlo_from_feature_matrix.py
```

---

## Current MarketState Research Findings

The current MarketState allocator behaves more like a risk-controlled participation engine than a pure alpha-maximizer.

Across strong bull markets, equal-weight and buy-and-hold benchmarks can outperform because the MarketState allocator is more defensive and may hold more cash.

Across rougher or mixed regimes, the MarketState allocator becomes more competitive because it reduces drawdowns and improves risk-adjusted behavior.

The key finding so far:

```text
In strong bull markets:
MarketState often underperforms benchmarks on raw return.

In rough or mixed markets:
MarketState can become competitive and may improve drawdown and Sharpe.
```

A major 2021-2024 test showed that the allocator can compete more effectively during hostile or mixed regimes. This suggests the system is useful as a defensive momentum allocator or risk-aware allocation overlay.

The current open question is not simply whether the system works. The better question is:

```text
How do we make the allocator adaptive enough to press harder in bull regimes
while preserving its defensive behavior in unstable regimes?
```

---

## Current Allocator Interpretation

The current MarketState allocator is best described as:

```text
defensive momentum allocator with entropy/volatility risk throttling
```

It does not yet try to maximize upside in all conditions.

It currently does well at:

- reducing drawdowns
- avoiding some dangerous states
- lowering exposure in chaotic regimes
- producing smoother equity curves
- becoming more useful in rougher market periods

It currently needs improvement in:

- upside participation during strong bull regimes
- gross exposure control
- portfolio-level regime awareness
- adaptive max-weight rules
- fallback allocation when the system is underexposed
- deciding when to behave more like equal-weight participation

---

## Next Planned Allocator Work

The next major research direction is Portfolio Regime Overlay v1.

The purpose is to make the allocator adaptive at the portfolio level.

Possible regime logic:

```text
RISK_ON:
    target gross exposure near 100%
    allow higher max weights
    trust momentum more
    reduce cash drag

NEUTRAL:
    use current MarketState behavior
    moderate caps
    normal signal scaling

RISK_OFF:
    lower gross exposure
    stricter posture caps
    block dangerous states
    preserve capital
```

Possible broad-market regime inputs:

```text
SPY above/below 200-day moving average
QQQ above/below 200-day moving average
SPY 63-day momentum
QQQ 63-day momentum
broad-market realized volatility
broad-market entropy
percentage of universe in RESTRICTED or CAPITAL_PRESERVATION
```

Planned allocator improvements:

```text
1. Portfolio Regime Overlay v1
2. Gross exposure diagnostics
3. Posture-based max weight caps
4. Equal-weight fallback for underexposed states
5. Score clipping
6. Risk-adjusted momentum
7. CUDA/CuPy backend for large matrix operations
8. GARCH validation mode for smaller selected universes
```

---

## Running a Basic Regime Backtest

```bash
python -m backtester.cli \
  --strategy regime \
  --ticker SPY \
  --start 2015-01-01 \
  --end 2024-12-31
```

---

## Run a Regime Backtest with Router and Options Overlay

```bash
python -m backtester.cli \
  --strategy regime \
  --ticker NVDA \
  --start 2015-01-01 \
  --end 2024-12-31 \
  --use-regime-router \
  --use-options-overlay \
  --output-root outputs/experiments/extreme_only_router
```

This writes output to:

```text
outputs/experiments/extreme_only_router/regime/NVDA/<RUN_ID>/
```

Generated files usually include:

```text
backtest.csv
equity_curve.png
```

---

## Conditional Options Overlay Experiment

The options overlay should not always be applied globally.

In testing, it helped high-volatility names like NVDA and TSLA, but dragged or did not help steadier names.

A ticker-gated overlay can be run like this:

```bash
for ticker in SPY QQQ AAPL MSFT NVDA TSLA; do
  python -m backtester.cli \
    --strategy regime \
    --ticker "$ticker" \
    --start 2015-01-01 \
    --end 2024-12-31 \
    --use-regime-router \
    --use-options-overlay \
    --options-overlay-tickers NVDA TSLA \
    --output-root outputs/experiments/conditional_options_overlay
done
```

Expected behavior:

```text
SPY, QQQ, AAPL, MSFT -> options overlay skipped
NVDA, TSLA           -> options overlay active
```

Then evaluate:

```bash
python scripts/strategy_scorecard.py outputs/experiments/conditional_options_overlay/regime \
  --equity-column combined_equity \
  --latest-only

python scripts/compare_equity_layers.py outputs/experiments/conditional_options_overlay/regime \
  --latest-only
```

---

## Dividend Capture Strategy

Event-driven trading around ex-dividend dates.

```bash
python -m backtester.cli \
  --strategy dividend \
  --tickers PG KO JNJ XOM CVX \
  --start 2018-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000
```

The dividend engine tracks:

- entry date
- ex-dividend date
- exit date
- dividend income
- price return
- total return
- trade-level PnL

---

## Research Scripts

### `scripts/strategy_scorecard.py`

Scans backtest output folders and ranks runs using performance metrics.

Metrics include:

- CAGR
- total return
- annualized volatility
- Sharpe
- max drawdown
- Calmar
- exposure
- exposure efficiency
- buy-and-hold comparison
- alpha versus buy-and-hold

Example:

```bash
python scripts/strategy_scorecard.py outputs/experiments/conditional_options_overlay/regime \
  --equity-column combined_equity \
  --latest-only
```

Useful equity columns:

```text
combined_equity
equity_strategy_equity
options_overlay_equity
```

`--latest-only` keeps only the newest run per strategy/ticker.

---

### `scripts/compare_equity_layers.py`

Compares strategy layers inside each backtest.

Main comparison:

```text
combined_equity vs equity_strategy_equity
```

This answers:

```text
Did the options overlay help or hurt?
```

Example:

```bash
python scripts/compare_equity_layers.py outputs/experiments/conditional_options_overlay/regime \
  --latest-only
```

Possible verdicts:

```text
HELPED
MOSTLY_HELPED
MIXED
HURT
UNCHANGED
```

---

### Other Scripts

- `run_regime_basket.py`: runs regime backtests across baskets of tickers.
- `summarize_regime_basket.py`: summarizes basket backtest outputs.
- `compare_regime_by_year.py`: produces year-by-year comparisons.
- `compare_regime_runs.py`: compares multiple regime runs.
- `backtest_options_overlay.py`: standalone options overlay experiment runner.

---

## Output Policy

Generated outputs are ignored by Git.

Ignored folders include:

```text
outputs/
results/
archive/old_backtests/
src/outputs/
wheelhouse/
__pycache__/
*.egg-info/
```

This keeps the repository focused on:

- source code
- scripts
- documentation
- configuration

The preferred generated-output structure is:

```text
outputs/
  experiments/
    <experiment_name>/
      regime/
        <TICKER>/
          <RUN_ID>/
            backtest.csv
            equity_curve.png
  feature_matrix/
    <experiment_name>/
      market_state_features.csv
      close_prices.csv
      metadata.csv
  monte_carlo/
    <experiment_name>/
      monte_carlo_trials.csv
      monte_carlo_distribution.csv
      monte_carlo_benchmark_distribution.csv
      monte_carlo_benchmark_comparison.csv
      monte_carlo_risk_stats.csv
      monte_carlo_equity_curves.csv
      plots/
        strategy_equity_curves_spaghetti.png
        ew_rebalance_equity_curves_spaghetti.png
        ew_buy_hold_equity_curves_spaghetti.png
        median_strategy_vs_benchmarks.png
```

Outputs can be regenerated and should not be committed unless a file is intentionally curated for documentation.

---

## Notes and Limitations

- Data currently comes from `yfinance`, which is convenient but not institutional-grade.
- The options overlay is simplified and experimental.
- Dividend capture logic is a naive baseline.
- Slippage and market impact are not fully modeled yet.
- Transaction costs are not fully modeled in the allocator research pipeline yet.
- The current allocator uses simple momentum scoring, not a finished multi-alpha score model.
- Universe selection can create bias, especially when testing high-performing modern tickers over earlier periods.
- Results should be treated as research output, not trading advice.

---

## Philosophy

Build fast.

Test ideas.

Score them honestly.

Benchmark everything.

Prefer explanations that survive comparison.

Keep what improves the system.

Reject what only looks good in isolation.

This repo is designed for experimentation, iteration, and gradual movement toward a more serious quant research platform.
