# Market Intelligence Engine

The Market Intelligence Engine converts messy market text into structured evidence.

It should not make trades directly. It produces features that the strategy layer can combine with price, volatility, market-fabric, and regime signals.

## Placement

- Source package: `src/backtester/intelligence/`
- CLI runners: `scripts/run_market_intelligence.py`
- Raw/manual text inputs: `data/intelligence/raw/`
- Generated model artifacts: `outputs/intelligence/`

## Run

```bash
python -m scripts.run_market_intelligence \
  --query PLTR \
  --input data/intelligence/raw/pltr_sample_news.jsonl \
  --peer-divergence 0.15 \
  --volume-shock 0.20 \
  --trend-damage 0.10
```

## Features

The generated CSV includes:

- `news_pressure`
- `macro_pressure`
- `sector_pressure`
- `idiosyncratic_pressure`
- `political_risk_pressure`
- `valuation_pressure`
- `sentiment_score`
- `regime_break_score`
- `confidence`
- `peer_divergence`
- `volume_shock`
- `trend_damage`

## Interpretation

- `regime_break_score < 0.30`: same regime, scale-in allowed if the price/amplitude setup agrees.
- `0.30 <= regime_break_score < 0.55`: caution, hold only.
- `0.55 <= regime_break_score < 0.75`: likely regime damage, do not average down.
- `0.75 <= regime_break_score`: thesis-break risk, reduce exposure or wait for a new setup.
