# Stock Backtester — Modular Quant Research Framework

A modular Python backtesting and research framework for testing trading strategies, volatility regimes, routing logic, and strategy overlays.

The project started as a simple stock backtester, but has grown into a research system for comparing strategy behavior across tickers, market regimes, and experimental branches.

The current architecture supports:

- Regime-based equity strategies
- Dividend/event-driven strategies
- GARCH-style volatility analytics
- Volatility regime routing
- Regime-aware position sizing
- Simplified options overlay experiments
- Conditional options-overlay gating by ticker
- Isolated experiment output folders
- Strategy scorecards and research comparison reports

Generated outputs are ignored by Git. The repository is meant to store source code, scripts, documentation, and reproducible research tools, not large backtest artifacts.

---

## Core Idea

The project is built around a research loop:

~~~text
strategy idea
    -> backtest
    -> isolated experiment output
    -> scorecard
    -> layer comparison
    -> decision: keep, modify, or reject
~~~

Instead of treating every backtest as a one-off script, this framework separates the system into:

- data loading
- strategy signal generation
- decision/routing logic
- execution/backtest engines
- risk and overlay logic
- research evaluation scripts

The long-term goal is to evolve toward a modular quant engine:

~~~text
strategies -> orthogonalization -> allocator -> risk -> execution
~~~

---

## Project Structure

~~~text
stock-backtester/
├── src/backtester/
│   ├── cli.py
│   ├── data.py
│   ├── metrics.py
│   ├── plot.py
│   ├── universes.py
│   │
│   ├── analytics/
│   │   ├── volatility.py
│   │   ├── volatility_state.py
│   │   └── options_data.py
│   │
│   ├── decision/
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
~~~

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

~~~bash
--strategy regime
--strategy dividend
--use-regime-router
--use-options-overlay
--options-overlay-tickers NVDA TSLA
--output-root outputs/experiments/<experiment_name>
~~~

---

### `src/backtester/data.py`

Data loading layer.

Currently handles price retrieval and formatting for the rest of the system.

---

### `src/backtester/analytics/`

Market-state analytics.

Key files:

- `volatility.py`: computes GARCH-style volatility metrics.
- `volatility_state.py`: helpers for classifying volatility states.
- `options_data.py`: options-related data helpers and experimental utilities.

---

### `src/backtester/decision/`

Decision logic and routing layer.

Key files:

- `regime_router.py`: converts volatility state into routing decisions.
- `position_sizing.py`: applies regime-aware risk scaling to equity exposure.
- `volatility_decision.py`: defines volatility decision schemas and EXTREME/HIGH/NORMAL/LOW style classification behavior.

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

~~~bash
python scripts/strategy_scorecard.py outputs/experiments/conditional_options_overlay/regime \
  --equity-column combined_equity \
  --latest-only
~~~

Useful equity columns:

~~~text
combined_equity
equity_strategy_equity
options_overlay_equity
~~~

`--latest-only` keeps only the newest run per strategy/ticker.

---

### `scripts/compare_equity_layers.py`

Compares strategy layers inside each backtest.

Main comparison:

~~~text
combined_equity vs equity_strategy_equity
~~~

This answers:

~~~text
Did the options overlay help or hurt?
~~~

Example:

~~~bash
python scripts/compare_equity_layers.py outputs/experiments/conditional_options_overlay/regime \
  --latest-only
~~~

Possible verdicts:

~~~text
HELPED
MOSTLY_HELPED
MIXED
HURT
UNCHANGED
~~~

---

### Other Scripts

- `run_regime_basket.py`: runs regime backtests across baskets of tickers.
- `summarize_regime_basket.py`: summarizes basket backtest outputs.
- `compare_regime_by_year.py`: produces year-by-year comparisons.
- `compare_regime_runs.py`: compares multiple regime runs.
- `backtest_options_overlay.py`: standalone options overlay experiment runner.

---

## Running the Project

Activate the environment:

~~~bash
source .venv/bin/activate
~~~

If needed, install the package in editable mode:

~~~bash
pip install -e .
~~~

Then check the CLI:

~~~bash
python -m backtester.cli --help
~~~

---

## Run a Basic Regime Backtest

~~~bash
python -m backtester.cli \
  --strategy regime \
  --ticker SPY \
  --start 2015-01-01 \
  --end 2024-12-31
~~~

---

## Run a Regime Backtest with Router and Options Overlay

~~~bash
python -m backtester.cli \
  --strategy regime \
  --ticker NVDA \
  --start 2015-01-01 \
  --end 2024-12-31 \
  --use-regime-router \
  --use-options-overlay \
  --output-root outputs/experiments/extreme_only_router
~~~

This writes output to:

~~~text
outputs/experiments/extreme_only_router/regime/NVDA/<RUN_ID>/
~~~

Generated files usually include:

~~~text
backtest.csv
equity_curve.png
~~~

---

## Run Conditional Options Overlay Experiment

The options overlay should not always be applied globally. In testing, it helped high-volatility names like NVDA and TSLA, but dragged or did not help steadier names.

A ticker-gated overlay can be run like this:

~~~bash
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
~~~

Expected behavior:

~~~text
SPY, QQQ, AAPL, MSFT -> options overlay skipped
NVDA, TSLA           -> options overlay active
~~~

Then evaluate:

~~~bash
python scripts/strategy_scorecard.py outputs/experiments/conditional_options_overlay/regime \
  --equity-column combined_equity \
  --latest-only

python scripts/compare_equity_layers.py outputs/experiments/conditional_options_overlay/regime \
  --latest-only
~~~

---

## Dividend Capture Strategy

Event-driven trading around ex-dividend dates.

~~~bash
python -m backtester.cli \
  --strategy dividend \
  --tickers PG KO JNJ XOM CVX \
  --start 2018-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000
~~~

The dividend engine tracks:

- entry date
- ex-dividend date
- exit date
- dividend income
- price return
- total return
- trade-level PnL

---

## Output Policy

Generated outputs are ignored by Git.

Ignored folders include:

~~~text
outputs/
results/
archive/old_backtests/
src/outputs/
wheelhouse/
__pycache__/
*.egg-info/
~~~

This keeps the repository focused on:

- source code
- scripts
- documentation
- configuration

The preferred generated-output structure is:

~~~text
outputs/
  experiments/
    <experiment_name>/
      regime/
        <TICKER>/
          <RUN_ID>/
            backtest.csv
            equity_curve.png
  research/
    scorecards and comparison reports
~~~

Outputs can be regenerated and should not be committed unless a file is intentionally curated for documentation.

---

## Current Research Direction

The project is moving toward a layered strategy engine:

~~~text
strategies -> decision/routing -> allocation -> risk -> execution
~~~

Current active research themes:

- volatility regime classification
- GARCH-based market-state routing
- regime-aware position sizing
- options overlays as conditional convexity exposure
- scorecard-based research evaluation
- separating base strategy performance from overlay contribution

---

## Notes and Limitations

- Data currently comes from `yfinance`, which is convenient but not institutional-grade.
- The options overlay is simplified and experimental.
- Dividend capture logic is a naive baseline.
- Slippage and market impact are not fully modeled yet.
- Results should be treated as research output, not trading advice.

---

## Philosophy

Build fast.  
Test ideas.  
Score them honestly.  
Keep what improves the system.  
Reject what only looks good in isolation.

This repo is designed for experimentation, iteration, and gradual movement toward a more serious quant research platform.
