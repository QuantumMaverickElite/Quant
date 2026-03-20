# Quant

A collection of quantitative finance experiments, research pipelines, and backtesting systems.

This repository is structured as a growing research environment rather than a single project. Each subdirectory represents a different idea, model, or system that is being explored, tested, and iterated on over time.

## Projects

### stock-backtester

A flexible backtesting engine for testing systematic trading strategies across equities and ETFs.

Focus areas:

* Momentum and regime-based strategies
* Parameter exploration and optimization
* Equity curve visualization
* Long-term historical testing (2005–present)

Outputs are organized by ticker and stored in:

```
stock-backtester/outputs/<TICKER>/
```

---

### dividend-capture

A research project exploring dividend capture strategies and their variations.

Core idea:
Buy before the ex-dividend date and sell after, attempting to capture dividend yield while minimizing price drop risk.

Current findings:

* Naive dividend capture is generally unprofitable
* Price drops tend to exceed dividend value (on average)
* Certain tickers and holding periods show partial recovery patterns
* Strategy may have more potential on the **short side** than long

This project is still exploratory and intended for experimentation rather than production trading.

---

## Philosophy

This repo is not about copying known strategies—it’s about:

* Testing ideas quickly
* Breaking assumptions
* Building intuition through data
* Iterating toward more robust systems

Some ideas will fail. That’s part of the process.

---

## Structure

```
quant/
├── stock-backtester/
├── dividend-capture/
```

Each project is self-contained, with its own:

* code
* outputs
* documentation

---

## Notes

* Outputs (CSVs, plots) are intentionally kept for analysis and comparison
* Filenames encode parameters for reproducibility
* Structure will evolve as systems become more sophisticated

---

## Future Direction

* Unified research framework across strategies
* Metadata-driven experiment tracking (instead of long filenames)
* Integration with data pipelines and model evaluation tools
* Expansion into multi-strategy portfolio systems

---

This is an evolving workspace.
