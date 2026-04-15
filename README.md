# Quant

A collection of quantitative finance experiments, research pipelines, and backtesting systems.

This repository is structured as a growing research environment rather than a single project. Each subdirectory represents a different idea, model, or system being explored, tested, and iterated on over time.

---

## Where to Start

If you're new to this repository:

1. Start with the main active system:
   stock-backtester/

2. Inside that project, the most important layers are:

- `src/backtester/strategies/`
- `src/backtester/engines/`
- `src/backtester/backtests/`

1. Example research modules include:

- regime-based backtesting
- dividend capture
- volatility strategy research

This repository is designed as a research workspace, so multiple ideas exist in parallel. Not every component is production-ready. The goal is exploration, iteration, and refinement.

---

## Projects

### stock-backtester

The main active system in this repository.

A modular backtesting framework for testing multiple classes of trading strategies across equities and ETFs.

Focus areas include:

- regime and momentum-based strategies
- event-driven strategies
- volatility strategy research
- backtest infrastructure and experiment tracking

Outputs are organized by strategy and timestamp so that experiments remain reproducible and do not overwrite one another.

---

### dividend-capture

A research project exploring dividend capture strategies and their variations.

Core idea:  
Buy before the ex-dividend date and sell after, attempting to capture dividend yield while minimizing price drop risk.

Current findings:

- naive dividend capture is generally unprofitable
- price drops often offset much of the dividend
- some tickers and holding periods show partial recovery patterns
- the strategy is more useful as a research baseline than a finished system

This project remains exploratory and is meant for experimentation rather than production use.

---

## Philosophy

This repo is not about copying known strategies. It is about:

- testing ideas quickly
- breaking assumptions
- building intuition through data
- iterating toward more robust systems

Some ideas will fail. That is part of the process.

---

## Structure

```
quant
├── dividend-capture
├── README.md
└── stock-backtester
```

Each project is self-contained, with its own:

- code
- outputs
- documentation

---

## Current Direction

The repository is moving toward a broader multi-strategy research framework, with emphasis on:

- cleaner experiment tracking
- better output organization
- modular strategy development
- future universe selection and portfolio construction

---

This is an evolving workspace.
