# Stock Backtester — Modular Quant Research Framework

## Start here

This is the main active quant research system. Use this map before opening a
script:

| Need | Start here |
| --- | --- |
| Mean reversion and peer spreads | [`src/backtester/signals/`](src/backtester/signals/README.md) and [`docs/large_universe_pipline.md`](docs/large_universe_pipline.md) |
| Volatility, entropy, and regime decisions | [`src/backtester/analytics/`](src/backtester/analytics/README.md) and [`src/backtester/context/`](src/backtester/context/README.md) |
| Correlation/deformation | [`src/backtester/correlation/`](src/backtester/correlation/README.md) |
| Allocators and backtest engines | [`src/backtester/engines/`](src/backtester/engines/README.md) |
| Intelligence | [`src/backtester/intelligence/`](src/backtester/intelligence/README.md) |
| Rust stress/matrix path | [`rust_engine/README.md`](rust_engine/README.md) |
| Combined signal research | [`docs/research_notes/COMBINED_SIGNAL_RESEARCH.md`](docs/research_notes/COMBINED_SIGNAL_RESEARCH.md) |
| Commands and pipelines | [`scripts/README.md`](scripts/README.md) |
| Offline validation | [`scripts/README.md`](scripts/README.md#tests) and the Phase 5 move note |
| Config and policies | [`configs/README.md`](configs/README.md) |
| Current/historical architecture | [`docs/README.md`](docs/README.md) and [`docs/reorg/CURRENT_ARCHITECTURE.md`](docs/reorg/CURRENT_ARCHITECTURE.md) |

Generated results remain under `outputs/`; data and cached matrices remain under
their existing contracts. This phase does not move either tree.

A modular Python research framework for testing trading strategies, market regimes, volatility and entropy features, Monte Carlo simulations, allocator rules, and CPU/GPU matrix-based portfolio experiments.

The project started as a simple stock backtester. It has grown into a research system for studying how strategies behave across tickers, regimes, sampled universes, rebalance rules, allocator logic, and experimental risk overlays.

The long-term goal is to evolve this repo into a serious quant research platform with the architecture:

```text
strategies -> signal processing -> allocator -> risk -> execution
```

The current research focus is the allocator layer.

---

## What This Project Does

This repository currently supports:

- Regime-based equity strategy backtests
- Dividend/event-driven strategy tests
- GARCH-style volatility analytics
- Fast realized-volatility analytics
- Return entropy and directional entropy analytics
- Volatility and entropy decision layers
- MarketState construction
- MarketState-driven portfolio backtests
- Feature-matrix based Monte Carlo simulations
- Equal-weight rebalance and buy-and-hold benchmarks
- Threshold rebalance allocator experiments
- Deterministic allocator selection
- CPU multiprocessing for faster experiments
- Experimental NumPy/CuPy backend abstraction
- Experimental CPU/GPU matrix batch operations
- Strategy scorecards and comparison scripts
- Simplified options overlay experiments
- Conditional options-overlay gating by ticker
- Isolated experiment output folders

Generated outputs are ignored by Git. The repository is meant to store source code, scripts, documentation, configuration, and reproducible research tools — not large experiment artifacts.

---

## Core Research Loop

The project is built around this research loop:

```text
strategy idea
    -> backtest
    -> isolated output folder
    -> scorecard
    -> benchmark comparison
    -> Monte Carlo validation
    -> bias/reproducibility audit
    -> decision: keep, modify, or reject
```

Instead of treating every backtest as a one-off script, the framework separates the system into:

```text
data loading
analytics / feature generation
signal generation
decision / routing logic
market-state construction
allocator simulation
execution / backtest engines
risk and overlay logic
research evaluation scripts
```

The important principle is that every idea should survive comparison. A strategy that looks good in isolation is not enough.

---

## Current Architecture

At a high level, the project is moving toward this structure:

```text
price data
    -> feature generation
    -> signal matrices
    -> market-state / regime logic
    -> allocator simulation
    -> portfolio weights
    -> equity curve
    -> benchmark comparison
    -> Monte Carlo validation
```

The current MarketState allocator pipeline is:

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

The newer matrix allocator research pipeline is moving toward:

```text
price matrix
    -> return matrix
    -> signal matrices
    -> normalized/ranked signals
    -> combined allocator score
    -> risk/diversification constraints
    -> portfolio weights
    -> portfolio return matrix
    -> summary statistics
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
│   │   ├── array_backend.py
│   │   ├── matrix_allocator_engine.py
│   │   ├── matrix_batch_ops.py
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
│   ├── build_market_state_feature_matrix.py
│   ├── monte_carlo_from_feature_matrix.py
│   ├── threshold_rebalance_fast_v2.py
│   ├── threshold_rebalance_fast_v3.py
│   ├── threshold_rebalance_matrix_engine.py
│   ├── benchmark_array_backend.py
│   ├── benchmark_matrix_batch_ops.py
│   ├── strategy_scorecard.py
│   ├── compare_equity_layers.py
│   └── test_*.py
│
├── docs/
├── archive/
├── outputs/       # ignored generated outputs
├── results/       # ignored old generated plots
├── assets/        # curated documentation assets only
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Environment Setup

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Install the package in editable mode if needed:

```bash
pip install -e .
```

Check the CLI:

```bash
python -m backtester.cli --help
```

Compile-check the project:

```bash
python -m compileall src/backtester scripts
```

---

## Main Systems

### MarketState System

The MarketState layer combines volatility and entropy into an allocator-facing object.

The core idea is:

```text
combined_multiplier = risk_multiplier * signal_trust_multiplier
```

Where:

```text
risk_multiplier          comes from volatility regime logic
signal_trust_multiplier  comes from entropy regime logic
combined_multiplier      scales the raw strategy score
```

MarketState can also control permissions:

```text
allow_new_equity_positions
allow_options
capital_posture
preferred_strategy
```

Common capital postures include:

```text
NORMAL
CAUTIOUS
DEFENSIVE
CAPITAL_PRESERVATION
RESTRICTED
```

The purpose of MarketState is to let the allocator react to market conditions without hardcoding every rule directly into a trading strategy.

### Entropy Engine

The entropy engine measures uncertainty in returns.

It currently uses two major ideas:

```text
Return entropy:
    How dispersed or abnormal return magnitudes are.

Directional entropy:
    How choppy or random the up/down sequence is.
```

Entropy regimes include:

```text
LOW
NORMAL
HIGH
EXTREME
```

The entropy decision layer can produce:

```text
signal_trust_multiplier
allow_new_signals
entropy_state_description
reason
```

The allocator uses this to decide how much it should trust raw momentum or strategy scores.

### Volatility Engines

The project uses two volatility concepts.

GARCH volatility is model-based. It attempts to estimate conditional volatility using recent shocks and recent volatility behavior. It is useful for deeper validation and smaller-universe research, but it is slower and can be fragile in large loops.

Fast volatility is a rolling-statistics proxy. It uses realized volatility, rolling z-scores, volatility percentiles, and spike flags. It is more useful for broad universe scans, feature matrix construction, Monte Carlo simulations, and future CPU/GPU matrix acceleration.

---

## Allocator Research

The current allocator research started with MarketState-adjusted scoring:

```text
raw momentum score * MarketState combined multiplier
```

This evolved into threshold rebalance experiments and matrix allocator experiments.

The current allocator work includes:

```text
threshold rebalance testing
portfolio size comparison
rebalance frequency comparison
Monte Carlo universe sampling
deterministic top-N selection
CPU multiprocessing
matrix-oriented simulation
experimental CPU/GPU batch operations
```

The main lesson so far is that the allocator behaves more like a defensive momentum allocator than a pure alpha maximizer.

In strong bull markets, equal-weight and buy-and-hold benchmarks can outperform because the allocator may hold too much cash or reduce exposure too aggressively.

In rougher or mixed regimes, the allocator can become more competitive because it reduces drawdowns and improves risk-adjusted behavior.

The open allocator question is:

```text
How do we make the allocator press harder in risk-on regimes
while preserving defensive behavior in unstable regimes?
```

---

## Deterministic Allocator Selection

Allocator selection must be reproducible across dependency versions.

A previous version used `np.argpartition` to select top-N candidates. That was fast, but it was unstable when scores tied. Different NumPy versions could choose tied candidates differently, which changed low-threshold rebalance paths and materially changed results.

The allocator selection path now uses deterministic tie-breaking:

```text
1. Higher score wins.
2. If scores tie, lower ticker column index wins.
```

This fixed the version-sensitive behavior between NumPy 1.26 and NumPy 2.x.

This matters especially for low-threshold experiments because threshold `0.00` rebalances constantly. Small differences in candidate ordering can compound through the full equity curve.

Reproducibility is now treated as part of the research system, not an afterthought.

---

## CPU / GPU Matrix Research

The project now has an experimental CPU/GPU abstraction layer.

### `src/backtester/engines/array_backend.py`

Selects either NumPy or CuPy through a common backend interface.

```text
backend="numpy" -> CPU arrays
backend="cupy"  -> NVIDIA CUDA arrays
```

This avoids spreading backend-specific logic throughout the project.

### `src/backtester/engines/matrix_batch_ops.py`

Contains reusable matrix operations that can run on either NumPy or CuPy.

Current operations include:

```text
compute_return_matrix
cross_sectional_rank_desc
top_n_mask_from_scores
equal_weight_from_mask
portfolio_returns_from_weights
equity_curve_from_returns
```

This file is not the final allocator. It is the math-kernel layer for future allocator research.

The long-term goal is:

```text
CPU:
    dates
    orchestration
    branching logic
    logging
    experiment control

GPU:
    large return matrices
    signal matrices
    top-N masks
    weight matrices
    portfolio return matrices
    batch portfolio evaluation
```

The GPU is not expected to help much on tiny 32-stock toy universes. It becomes useful when the project scales toward thousands of stocks, long histories, and large batched matrix operations.

---

## Important Benchmark Lesson

Small universe benchmark:

```text
32 tickers:
    NumPy wins
    CuPy overhead dominates
```

Large synthetic universe benchmark:

```text
12,800 tickers:
    CuPy wins
    GPU becomes useful for broad matrix operations
```

This means the project should not blindly force GPU into every script. The correct approach is hybrid:

```text
Use CPU for control flow.
Use GPU for large matrix batches.
Avoid repeated CPU/GPU data transfers.
Do not cache giant arrays unless necessary.
```

---

## Common Commands

### Basic Regime Backtest

```bash
python -m backtester.cli \
  --strategy regime \
  --ticker SPY \
  --start 2015-01-01 \
  --end 2024-12-31
```

### Regime Backtest with Router and Options Overlay

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

### Dividend Capture Strategy

```bash
python -m backtester.cli \
  --strategy dividend \
  --tickers PG KO JNJ XOM CVX \
  --start 2018-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000
```

### Build MarketState Feature Matrix

```bash
python scripts/build_market_state_feature_matrix.py \
  -t SPY QQQ DIA IWM AAPL MSFT NVDA META AMZN GOOGL JPM COST WMT XOM CVX KO PG JNJ \
  --data-start 2015-01-01 \
  --bt-start 2018-01-01 \
  --bt-end 2026-01-01 \
  --rebalance M \
  --output-dir outputs/feature_matrix/market_state_2018_2026_quality
```

### Monte Carlo from Feature Matrix

```bash
python research/threshold_rebalance/monte_carlo_from_feature_matrix.py \
  --feature-path outputs/feature_matrix/market_state_2018_2026_quality/market_state_features.csv \
  --price-path outputs/feature_matrix/market_state_2018_2026_quality/close_prices.csv \
  --runs 100 \
  --sample-size 8 \
  --capital 10000 \
  --max-weight 0.35 \
  --output-dir outputs/monte_carlo/feature_matrix_2018_2026_quality_benchmark_max35
```

### Fast Threshold Rebalance v3

```bash
python scripts/threshold_rebalance_fast_v3.py \
  --runs 1000 \
  --sample-size 24 \
  --portfolio-size 8 \
  --thresholds 0.00 0.01 0.03 0.05 0.075 0.10 0.15 0.20 \
  --save-mode none \
  --workers 4 \
  --progress-every 100
```

### Matrix Threshold Engine

```bash
python scripts/threshold_rebalance_matrix_engine.py \
  --runs 1000 \
  --sample-size 24 \
  --portfolio-size 8 \
  --thresholds 0.00 0.01 0.03 0.05 0.075 0.10 0.15 0.20 \
  --save-mode none \
  --workers 4 \
  --progress-every 100
```

### Benchmark NumPy vs CuPy Backend

```bash
python scripts/benchmark_array_backend.py \
  --backend numpy \
  --repeats 100 \
  --tile-tickers 400 \
  --tile-dates 1

python scripts/benchmark_array_backend.py \
  --backend cupy \
  --repeats 100 \
  --tile-tickers 400 \
  --tile-dates 1
```

### Benchmark Matrix Batch Ops

```bash
python scripts/benchmark_matrix_batch_ops.py \
  --backend numpy \
  --repeats 5 \
  --tile-tickers 400 \
  --tile-dates 1

python scripts/benchmark_matrix_batch_ops.py \
  --backend cupy \
  --repeats 5 \
  --tile-tickers 400 \
  --tile-dates 1
```

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

The main repository should contain:

```text
source code
scripts
documentation
configuration
small curated examples if needed
```

The main repository should not contain:

```text
large Monte Carlo outputs
per-run folders
spaghetti plots from every experiment
temporary debug outputs
large intermediate matrices
```

Preferred save behavior:

```text
--save-mode none:
    no files; console output only

--save-mode compact:
    summary CSV + trial CSV + small metadata

--save-mode plots:
    compact files + selected plots

--save-mode full:
    full curves/spaghetti outputs; use intentionally
```

Large or important baselines should be compressed and stored outside the main repo, preferably in:

```text
private artifact repo
cloud drive
external drive
object storage
```

The project should preserve valuable baselines without allowing local disk usage to grow out of control.

---

## Artifact Policy

Research artifacts should be treated separately from source code.

Suggested structure:

```text
Main code repo:
    code
    scripts
    docs
    configs
    small examples

Private artifact storage:
    compressed baseline archives
    important plots
    selected CSV summaries
    experiment manifests
```

Useful artifact bundles include:

```text
threshold_summary.csv
threshold_trials.csv
selected comparison plots
important spaghetti plots
experiment manifest
input file hashes
dependency versions
code commit hash
```

Do not archive every temporary debug run. Save only experiments that are meaningful enough to become future baselines.

---

## Current Limitations

This is a research framework, not a production trading system.

Important limitations:

```text
Data currently comes mostly from yfinance.
Slippage and market impact are not fully modeled.
Transaction costs are not fully modeled in all allocator paths.
Options overlay logic is simplified and experimental.
Dividend capture logic is a naive baseline.
The current allocator is not a finished multi-alpha model.
Current universes can be biased toward personally selected stocks and past winners.
Broad-universe validation is still required.
Lookahead bias and selection bias still need explicit audit tools.
```

Results should be treated as research output, not trading advice.

---

## Current Research Direction

Near-term priorities:

```text
1. Keep output storage under control.
2. Preserve important baselines as compressed artifacts.
3. Expand matrix batch ops into reusable allocator primitives.
4. Add multi-signal matrix support.
5. Add correlation and risk matrix operations.
6. Add experiment manifests for reproducibility.
7. Audit lookahead bias and selection bias.
8. Test broader, less hand-picked universes.
9. Build a stronger allocator that combines many signals.
10. Use GPU only where matrix scale justifies it.
```

The future allocator should not be hardcoded around one signal. It should eventually combine:

```text
momentum
volatility
entropy
correlation
drawdown behavior
regime sensitivity
dividend events
buybacks
splits
earnings behavior
liquidity
sector or cluster exposure
macro/rate sensitivity
```

The goal is not just to pick the highest-scoring stocks. The goal is to build an allocator that can decide:

```text
Which signals matter right now?
How correlated are these candidates?
How much exposure should the portfolio take?
What risks are hidden in this basket?
Should the system press risk-on or defend capital?
```

---

## Mathematical Documentation

The project includes a dedicated math reference explaining the formulas behind the signals, engines, risk layers, allocation logic, and backtest metrics.

See:

- [Strategy Math and Signal Definitions](docs/strategy_math.md)

## Philosophy

Build fast.

Test honestly.

Benchmark everything.

Prefer reproducible results over lucky results.

Do not trust a backtest until it survives comparison.

Do not trust an allocator until it survives broader universes.

Keep source code clean.

Keep artifacts separate.

Save only what is worth keeping.

Reject what only looks good in isolation.

This repo is designed for experimentation, iteration, and gradual movement toward a serious quant research platform.
