# Project Architecture

The project is a modular quant research framework. It began as a stock backtester and has grown into a research system for testing strategies, market regimes, allocator rules, Monte Carlo simulations, and CPU/GPU matrix experiments.

The long-term target architecture is:

```text
strategies -> signal processing -> allocator -> risk -> execution
```

The current research focus is the allocator layer.

## High-Level Flow

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

## Core Layers

### Data Layer

Responsible for pulling, formatting, and aligning price data.

Important files:

```text
src/backtester/data.py
src/backtester/universes.py
```

### Analytics Layer

Computes features such as volatility, entropy, and other signal inputs.

Important folder:

```text
src/backtester/analytics/
```

### Decision Layer

Converts raw analytics into allocator-facing decisions, permissions, and state.

Important folder:

```text
src/backtester/decision/
```

### Engine Layer

Runs backtests, event simulations, matrix allocator simulations, and experimental CPU/GPU operations.

Important folder:

```text
src/backtester/engines/
```

### Strategy Layer

Contains strategy-specific signal logic.

Important folder:

```text
src/backtester/strategies/
```

### Script Layer

Contains research scripts for building feature matrices, running Monte Carlo tests, comparing strategies, and benchmarking CPU/GPU behavior.

Important folder:

```text
scripts/
```

## Current Research Direction

The project is moving from one-off backtests toward allocator research.

The newer allocator pipeline is:

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

The goal is not to hardcode one strategy. The goal is to build reusable components that can combine many future signals.
