# Market State Engine Notes

## Core Architecture

Long-term architecture:

strategies -> orthogonalization -> allocator -> risk -> execution

Current pipeline:

price data
-> GARCH volatility metrics
-> volatility decision layer
-> regime router
-> position sizing / options overlay
-> backtest output

## What Exists Now

### 1. GARCH Volatility Metrics

Main files:

- src/backtester/analytics/volatility.py
- src/backtester/analytics/volatility_state.py

These compute:

- garch_vol_annualized
- vol_zscore
- vol_percentile
- vol_regime
- vol_spike_flag
- vol_high_flag

### 2. GARCH Manifold Visualizer

Main file:

- src/backtester/visuals/garch_state.py

Purpose:

- visualize volatility regimes
- observe volatility clustering
- study transitions between normal / high / extreme states
- record visual playback

### 3. Volatility Decision Layer

Main file:

- src/backtester/decision/volatility_decision.py

Current rough behavior:

- LOW -> mean_reversion, risk 1.10
- NORMAL -> standard, risk 1.00
- HIGH -> breakout, risk 0.70
- EXTREME -> defensive_or_long_vol, risk 0.35

### 4. Regime Router

Main file:

- src/backtester/decision/regime_router.py

Right now it only uses volatility decisions.

Later it should combine:

- volatility regime
- H-Vol pressure
- correlation regime
- entropy
- ergodicity
- liquidity state
- direction / trend state

### 5. Position Sizing

Main file:

- src/backtester/decision/position_sizing.py

This scales base equity exposure using the router risk multiplier.

Example:

base position = 1.00
route multiplier = 0.70
final exposure = 0.70

### 6. Options Overlay Engine

Main file:

- src/backtester/engines/options_overlay_engine.py

This extracts the old standalone volatility options prototype into a reusable engine.

It generates simplified long-vol signals:

- STRADDLE
- STRANGLE
- NO_TRADE
- HOLD

The options overlay is currently a simplified research approximation. It is not a realistic options pricing/fill model yet.

### 7. CLI Integration

Main file:

- src/backtester/cli.py

Supported modes:

python -m backtester.cli --ticker SPY --strategy regime

python -m backtester.cli --ticker SPY --strategy regime --use-regime-router

python -m backtester.cli --ticker SPY --strategy regime --use-regime-router --use-options-overlay

The CLI can now run:

- baseline regime strategy
- router-scaled regime strategy
- router-scaled regime strategy + options overlay

## Research Scripts

Basic tests:

- scripts/test_volatility_decision.py
- scripts/test_real_volatility_decision.py
- scripts/test_regime_router.py
- scripts/test_position_sizing.py
- scripts/test_options_overlay.py

Backtest / comparison scripts:

- scripts/backtest_options_overlay.py
- scripts/compare_regime_runs.py
- scripts/run_regime_basket.py
- scripts/summarize_regime_basket.py
- scripts/compare_regime_by_year.py

## Current Research Findings

The current market-state system works mechanically.

Confirmed:

- GARCH metrics work.
- Volatility decisions work.
- Regime router works.
- Position scaling works.
- Options overlay works.
- CLI integration works.
- Basket testing works.
- Yearly diagnostics work.

But the current decision policy is too naive.

Current issue:

- The router treats volatility mostly as danger.
- HIGH volatility reduces exposure.
- EXTREME volatility reduces exposure hard.

This lowers volatility, but often gives up too much upside.

Basket tests on SPY, QQQ, and AAPL showed:

- baseline usually wins on CAGR and final equity
- router lowers volatility
- router does not consistently improve Sharpe
- options overlay is not broadly additive yet

Yearly diagnostics showed:

- router helps in some years
- router hurts in strong rally / recovery years
- options overlay can help in some high-volatility years

So the infrastructure is useful, but the current policy is not yet alpha-positive.

## Important Interpretation

The baseline strategy is currently the trader.

The router should probably become a risk officer, not a permanent trader.

Instead of:

router always modifies exposure

future versions should test:

router usually does nothing
router intervenes only during truly dangerous market states

## Next Experiment

Do not tune thresholds aggressively.

Next clean experiment:

EXTREME-only router

Proposed rule:

- LOW -> risk 1.00
- NORMAL -> risk 1.00
- HIGH -> risk 1.00
- EXTREME -> risk 0.50

Hypothesis:

The baseline strategy should remain mostly untouched.
The router should only reduce risk during truly abnormal volatility.
This may preserve upside while still reducing crash exposure.

Test across:

- SPY
- QQQ
- AAPL
- MSFT
- NVDA
- TSLA

Compare:

- baseline
- extreme-only router
- extreme-only router + options overlay

Do not tune based on one ticker.

## Later Ideas

After the EXTREME-only test:

1. Direction-aware routing
   HIGH volatility + bullish momentum -> allow exposure
   HIGH volatility + bearish momentum -> reduce exposure

2. H-Vol Pressure System
   liquidity density
   time compression
   realized volatility
   pressure gradient
   expansion probability

3. Correlation Regime Engine
   rolling correlation matrix
   cluster detection
   systemic risk detection

4. Entropy / Ergodicity Engine
   structure vs randomness
   time-average vs ensemble-average divergence

5. Better Options Overlay
   real implied volatility data
   better premium modeling
   realistic holding / exit rules
   strategy-specific capital allocation

6. Multi-line comparison charts
   buy-and-hold
   baseline
   router
   router + options

## Reminder

The goal is not to force the market-state layer to beat the baseline immediately.

The goal is to build a disciplined research system where every added layer must prove itself against the baseline.
