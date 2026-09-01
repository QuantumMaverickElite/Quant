# Market Intelligence v5.0.1 - Smoke Coverage Fix

## Purpose

The v5.0 stress runner still used the older hardcoded minimum of 20 signal dates. That is correct for real research, but too strict for a small smoke test. v5.0.1 adds `--min-signal-dates` so a smoke run can explicitly lower the threshold without weakening full research runs.

## Install

From `~/projects/quant`:

```bash
unzip -o ~/Downloads/market_intelligence_v5_0_1_clean_overlay.zip
cp market_intelligence_v5_0_1_overlay/scripts/run_historical_intelligence_stress.py stock-backtester/scripts/run_historical_intelligence_stress.py
cp market_intelligence_v5_0_1_overlay/docs/market_intelligence_v5_0_1.md stock-backtester/docs/market_intelligence_v5_0_1.md
cd stock-backtester
python -m compileall -q scripts/run_historical_intelligence_stress.py
```

## Smoke Run

Use `--min-signal-dates 5` for the small v5 SEC/news smoke:

```bash
python -m scripts.run_historical_intelligence_stress \
  --signals outputs/signals/mean_reversion_latest_with_intelligence.parquet \
  --work-dir outputs/intelligence/training_runs/v5_sec_news_smoke \
  --start 2025-10-01 \
  --end 2026-05-28 \
  --max-dates 8 \
  --min-signal-dates 5 \
  --top-n-per-date 25 \
  --download-prices \
  --fetch-sec \
  --sec-user-agent "stock-backtester elijah.alayev@gmail.com" \
  --news-sources data/intelligence/historical/raw/news_eval_2025_2026_merged_scored.jsonl \
  --score-sentiment \
  --sentiment-backend heuristic \
  --iterations 500 \
  --equity-iterations 500 \
  --train-days-list 60 126 \
  --embargo-days-list 10 \
  --alpha-list 10 \
  --model-types logistic \
  --min-train-rows-list 50 \
  --top-ns 5 10 20 \
  --return-cols next_5d_return next_10d_return \
  --skip-existing \
  --keep-going
```

For real research, keep the default `--min-signal-dates 20` or raise it.
