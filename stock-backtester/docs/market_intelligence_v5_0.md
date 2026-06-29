# Market Intelligence v5.0 - Multi-Source Training Panel

## Purpose

This overlay expands the ML/NLP research panel beyond a single news provider.

The issue is real: if one provider dominates, the model can learn provider syntax, coverage bias, or article-selection quirks. The objective is to train on event patterns, not one vendor's writing style.

v5.0 adds:

- SEC EDGAR support inside the historical stress runner;
- separate SEC feature joining before ML calibration;
- pass-through controls for Finnhub, Massive, NewsAPI, Polygon, and Alpha Vantage;
- source-mix audits to measure provider concentration and query coverage.

SEC filings are not mixed into the news sentiment file. They are joined as structured filing features. News and analyst feeds are merged/deduped/scored separately.

## Files

- `scripts/run_historical_intelligence_stress.py`
  - adds `--fetch-sec`, `--sec-sources`, `--sec-user-agent`, `--sec-forms`, and `--sec-sleep-seconds`;
  - builds SEC rolling features and trains on SEC-enriched labeled signals;
  - still supports multi-provider news through `--fetch-providers`, `--include-massive`, `--include-newsapi`, and `--include-polygon`.
- `scripts/run_multi_period_intelligence_research.py`
  - passes SEC and expanded provider controls through to each period.
- `scripts/audit_historical_source_mix.py`
  - writes provider summaries, query/provider matrices, month/provider matrices, and top-domain reports.
- `scripts/score_ml_research_gates.py`
  - retained from v4.9 for validation/permutation promotion gates.

## Install

From `~/projects/quant`:

```bash
unzip -o ~/Downloads/market_intelligence_v5_0_clean_overlay.zip
cp market_intelligence_v5_0_overlay/scripts/run_historical_intelligence_stress.py stock-backtester/scripts/run_historical_intelligence_stress.py
cp market_intelligence_v5_0_overlay/scripts/run_multi_period_intelligence_research.py stock-backtester/scripts/run_multi_period_intelligence_research.py
cp market_intelligence_v5_0_overlay/scripts/audit_historical_source_mix.py stock-backtester/scripts/audit_historical_source_mix.py
cp market_intelligence_v5_0_overlay/scripts/score_ml_research_gates.py stock-backtester/scripts/score_ml_research_gates.py
cp market_intelligence_v5_0_overlay/docs/market_intelligence_v5_0.md stock-backtester/docs/market_intelligence_v5_0.md
cd stock-backtester
python -m compileall -q scripts
```

## Recommended Multi-Period Run

This uses SEC, Finnhub, and Massive. Add Polygon/NewsAPI/Alpha only if the API keys and rate limits are ready.

```bash
mkdir -p outputs/intelligence/training_runs/multi_period_ml_research_v5

nohup python -m scripts.run_multi_period_intelligence_research \
  --signals outputs/signals/mean_reversion_latest_with_intelligence.parquet \
  --work-root outputs/intelligence/training_runs/multi_period_ml_research_v5 \
  --periods \
    2020_2021=2020-01-01:2021-12-31 \
    2022_2023=2022-01-01:2023-12-31 \
    2024_2026=2024-01-01:2026-05-28 \
  --download-prices \
  --fetch-sec \
  --sec-user-agent "stock-backtester elijah.alayev@gmail.com" \
  --fetch-news \
  --fetch-providers finnhub_news finnhub_recommendations \
  --include-massive \
  --iterations 20000 \
  --equity-iterations 10000 \
  --train-days-list 126 252 \
  --embargo-days-list 10 20 \
  --alpha-list 3 10 30 \
  --model-types logistic \
  --min-train-rows-list 100 200 \
  --skip-existing \
  --keep-going \
  > outputs/intelligence/training_runs/multi_period_ml_research_v5/run.log 2>&1 &
```

Optional provider add-ons:

```bash
--include-newsapi
--include-polygon
--include-alpha-vantage
```

Use those only when `NEWSAPI_KEY`, `POLYGON_API_KEY`, or `ALPHA_VANTAGE_API_KEY` are set and the rate limits are acceptable.

## Monitor

```bash
tail -f outputs/intelligence/training_runs/multi_period_ml_research_v5/run.log
cat outputs/intelligence/training_runs/multi_period_ml_research_v5/multi_period_manifest.csv
pgrep -af run_multi_period_intelligence_research
```

## Source-Mix Audit

Run this against merged or raw news files:

```bash
python -m scripts.audit_historical_source_mix \
  --inputs \
    outputs/intelligence/training_runs/multi_period_ml_research_v5/2022_2023/news_2022-01-01_2023-12-31_providers.jsonl \
    outputs/intelligence/training_runs/multi_period_ml_research_v5/2022_2023/news_2022-01-01_2023-12-31_massive.jsonl \
  --out-dir outputs/intelligence/training_runs/multi_period_ml_research_v5/2022_2023/source_audit \
  --label news_2022_2023 \
  --max-provider-share 0.60
```

Interpretation:

- if one provider is above 60% of rows, treat the model as provider-dependent until proven otherwise;
- if many tickers have fewer than 2 providers, those tickers should be downweighted or inspected before promotion;
- if a candidate works only when one provider is present, it is not ready for live use.

## Promotion Gate

Do not promote a policy because one period/top-N result looks good. Require:

- positive validation lift across at least two periods;
- non-negative p05 lift if using `--require-positive-p05`;
- permutation p-value at or below 0.05;
- true lift above shuffled-null p95;
- no single provider dominating the source audit.

The current policy remains research-only until it passes those gates.
