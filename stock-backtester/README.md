# Stock Backtester — Multi-Strategy Quant Framework

A modular Python-based backtesting system for experimenting with both **continuous trading strategies** and **event-driven strategies**.

This project currently supports:

- **Regime-based strategies** (momentum + mean reversion + crash logic)
- **Dividend capture strategies** (event-driven trades around ex-dividend dates)

---

## 🧠 Core Idea

Most retail backtesters only support one type of strategy.

This system is built to handle **multiple strategy classes**:

- **Position-based (continuous exposure)**  
  → e.g. momentum, mean reversion, leverage

- **Event-based (discrete trades)**  
  → e.g. dividend capture, earnings plays, macro events

---

## 🏗️ Project Structure

```
stock-backtester/
├── src/backtester/
│
│   ├── cli.py                 # Entry point (strategy selection)
│
│   ├── data.py                # Data loading (prices + dividends)
│
│   ├── engines/
│   │   ├── position_engine.py # Continuous backtesting engine
│   │   └── event_engine.py    # Event-driven trade engine
│
│   ├── strategies/
│   │   ├── position_strategies.py  # Momentum / streak logic
│   │   └── event_strategies.py     # Dividend capture logic
│
│   ├── models/
│   │   └── trade_result.py    # Data structures (results)
│
│   ├── utils.py              # Shared utilities
│   ├── metrics.py            # Performance metrics
│   ├── plot.py               # Equity curve plotting
│   └── universes.py          # (future) ticker group definitions
│
├── outputs/                  # Generated CSVs + plots (ignored)
├── results/                  # Curated outputs (optional)
├── requirements.txt
└── README.md
```

---

## 🚀 How to Run

### Activate environment

```bash
source .venv/bin/activate
```

---

## 📈 Regime Strategy (Default)

Momentum + mean reversion + crash detection + adaptive leverage

```bash
MPLBACKEND=Agg PYTHONPATH=src python -m backtester.cli \
  --strategy regime \
  --ticker SPY
```

### Output

- Equity curve plot
- CSV with:
  - price
  - exposure
  - returns
  - equity

---

## 💰 Dividend Capture Strategy

Event-driven trading around ex-dividend dates

```bash
PYTHONPATH=src python -m backtester.cli \
  --strategy dividend \
  --tickers PG KO JNJ XOM CVX \
  --start 2018-01-01 \
  --end 2026-01-01 \
  --hold-days 1 \
  --capital 10000
```

### Output

- Trade-level CSV
- Summary metrics:
  - total trades
  - win rate
  - average return
  - total PnL

---

## ⚙️ Strategy Details

### Regime Strategy

- 50-day momentum filter
- Mean reversion via streak logic
- Crash detection using 5-day drops
- Adaptive leverage when momentum is negative

---

### Dividend Strategy

For each ex-dividend event:

1. Buy 1 day before ex-date  
2. Collect dividend  
3. Sell after N trading days  

Tracks:

- price movement
- dividend income
- total return
- drop ratio (price drop vs dividend)

---

## 🔥 Why This Project Matters

This is not just a backtester — it's a **framework**.

It allows:

- comparing fundamentally different strategy types
- combining signals (future work)
- building a research pipeline for quant ideas

---

## 📌 Future Improvements

- Combine regime + dividend strategies
- Add transaction cost modeling to dividend trades
- Portfolio-level capital allocation
- Strategy stacking / ensemble models
- Custom universes (S&P sectors, dividend aristocrats, etc.)
- Risk management layer

---

## ⚠️ Notes

- Uses `yfinance` (not perfect data quality)
- No slippage modeling yet
- Dividend strategy is currently **naive baseline**

---

## 🧪 Philosophy

Build fast → test ideas → refine → iterate

This repo is designed for **experimentation and iteration**, not perfection.

---

## 📊 Status

✔ Modular architecture  
✔ Multi-strategy support  
✔ CLI interface  
✔ Clean separation of concerns  

🚧 Strategy combination (next step)

---
