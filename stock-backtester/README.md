# Stock Backtester — Multi-Regime Strategy  
Momentum + Crash Trigger + Adaptive Leverage

A lightweight Python backtesting engine that:

- Downloads historical data using `yfinance`
- Generates exposure with momentum + streak + crash logic
- Applies leverage rules
- Simulates transaction costs
- Exports CSV + equity curve plots vs buy & hold

---

# PROJECT STRUCTURE

```
stock-backtester/
├── src/backtester/
│   ├── cli.py
│   ├── strategies.py
│   ├── metrics.py
│   └── plot.py
├── outputs/        # auto-generated (ignored by git)
├── results/        # tracked showcase plots (optional)
├── requirements.txt
└── README.md
```

---

# HOW TO RUN THE PROJECT

## 1) Enter the project

From the repo root:

```bash
cd stock-backtester
```

---

## 2) Create virtual environment (if needed)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If it already exists:

```bash
source .venv/bin/activate
```

---

## 3) Run default backtest (SPY)

Always use module mode:

```bash
MPLBACKEND=Agg PYTHONPATH=src python -m backtester.cli
```

This will:

- Print performance metrics
- Save CSV
- Save equity curve plot

Outputs go to:

```
stock-backtester/outputs/
```

---

# DEBUG MODE

Print exposure statistics:

```bash
MPLBACKEND=Agg PYTHONPATH=src python -m backtester.cli --debug
```

---

# RUN DIFFERENT STOCKS

Example:

```bash
MPLBACKEND=Agg PYTHONPATH=src python -m backtester.cli --ticker QQQ
```

```bash
MPLBACKEND=Agg PYTHONPATH=src python -m backtester.cli --ticker NVDA
```

```bash
MPLBACKEND=Agg PYTHONPATH=src python -m backtester.cli --ticker TSLA
```

```bash
MPLBACKEND=Agg PYTHONPATH=src python -m backtester.cli --ticker AAPL
```

---

# RUN MULTIPLE STOCKS

```bash
for t in SPY QQQ NVDA TSLA AAPL; do
  MPLBACKEND=Agg PYTHONPATH=src python -m backtester.cli --ticker "$t"
done
```

---

# STRATEGY PARAMETER TESTING

## Change momentum lookback

```bash
MPLBACKEND=Agg PYTHONPATH=src python -m backtester.cli --lookback 100
```

---

## Adjust streak logic

```bash
MPLBACKEND=Agg PYTHONPATH=src python -m backtester.cli \
  --down-days 3 \
  --up-days 2
```

---

## Modify crash sensitivity

```bash
MPLBACKEND=Agg PYTHONPATH=src python -m backtester.cli \
  --crash-week-drop 0.10 \
  --crash-hold-days 7
```

---

## Adjust leverage

```bash
MPLBACKEND=Agg PYTHONPATH=src python -m backtester.cli --down-leverage 1.0
```

---

# OUTPUT FILES

Each run produces:

```
outputs/*_backtest.csv
outputs/*_equity_curve.png
```

CSV contains:

- close price
- exposure
- strategy return
- equity curve

---

# VIEWING CHARTS

## Open most recent plot for a ticker

```bash
imv "$(ls -t outputs/QQQ_*equity_curve.png | head -n 1)"
```

---

## Open all plots for a ticker

```bash
imv outputs/QQQ_*equity_curve.png
```

---

## Open multiple stocks

```bash
imv outputs/NVDA_*equity_curve.png \
    outputs/TSLA_*equity_curve.png \
    outputs/AAPL_*equity_curve.png
```

---

# INSTALL IMAGE VIEWER (Gentoo)

```bash
sudo emerge media-gfx/imv
```

---

# COMMON ERRORS

## ModuleNotFoundError: backtester

Always run with:

```bash
PYTHONPATH=src python -m backtester.cli
```

Never run:

```bash
python cli.py
```

---

## Plots not saving

Always include:

```bash
MPLBACKEND=Agg
```

---

# GIT HYGIENE

Recommended `.gitignore` entries:

```
outputs/
.venv/
src/*.egg-info/
```

If you want to track showcase images:

```
results/
```

Workflow:

1. Run experiments → outputs/
2. Copy best plots → results/
3. Commit results
4. Keep outputs ignored

---

# FULL EXAMPLE SESSION

```bash
cd stock-backtester
source .venv/bin/activate

for t in SPY NVDA TSLA; do
  MPLBACKEND=Agg PYTHONPATH=src python -m backtester.cli --ticker "$t"
done

imv outputs/SPY_*equity_curve.png
```

---

Built for fast quant strategy iteration and controlled experimentation.

