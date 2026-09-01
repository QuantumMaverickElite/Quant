# Market Intelligence Experiment Summary - 2026-06-23

## Objective

Test whether the market-intelligence / NLP sentiment layer improves the existing volatility, entropy, correlation, and mean-reversion allocator.

## Tested Files

- Baseline strategy source: `outputs/signals/mean_reversion_signals_market_common_stock_only_v3_context_adjusted.parquet`
- Intelligence-adjusted latest signals: `outputs/signals/mean_reversion_latest_with_intelligence.parquet`
- Allocator-ready heuristic NLP signals: `outputs/signals/mean_reversion_allocator_intelligence_v2.parquet`
- Evaluated and outcome-labeled slice: `outputs/signals/mean_reversion_allocator_intelligence_v2_evaluated_labeled.parquet`
- ML-calibrated diagnostic output: `outputs/signals/mean_reversion_allocator_intelligence_ml_calibrated.parquet`

## Current Test Scope

This is a current evaluated news/signal slice, not a full historical point-in-time NLP backtest.

- Evaluated rows: 73
- Evaluated tickers: 50
- Main signal date: 2026-05-28
- Valid return horizons used: 5 trading days and 10 trading days
- `next_20d_return` was not yet usable for this slice

## Best Current Result

Best operating point so far:

- Horizon: `next_10d_return`
- Portfolio size: top 20
- Allocation assumption: equal weight
- Cash example: `$10,000`

| Ranking | Mean 10d Return | Approx. PnL on $10,000 | Avg Drawdown |
|---|---:|---:|---:|
| Baseline allocator | 0.8706% | +$87.06 | -$508.44 |
| Heuristic NLP allocator | 3.3747% | +$337.47 | -$360.21 |
| ML-calibrated diagnostic allocator | 1.3302% | +$133.02 | -$485.76 |

Heuristic NLP improvement over baseline:

- Return improvement: +2.5041 percentage points
- Dollar improvement on $10,000: +$250.41
- Drawdown improvement on $10,000: about +$148.23 less average drawdown

## Monte Carlo Grid Result

The strongest robustness result was top 20 over 10 trading days:

- Probability heuristic NLP beats baseline: about 87%
- Probability heuristic NLP beats random portfolio: about 99.8%
- Probability heuristic NLP improves drawdown: about 82%

## Why NLP Helped

The improvement mostly came from risk filtering, not from perfect winner prediction.

Dropped from baseline top 20:

- `AMBA`: 10d return -28.35%, about -$141.77 contribution on a $10,000 / 20 equal-weight basket
- `TRMB`: 10d return -8.96%, about -$44.79 contribution
- `PNR`: 10d return +1.74%, about +$8.69 contribution, so this drop was a mistake

Entered NLP top 20:

- `MOH`: about +$42.64 contribution
- `CZNC`: about +$17.01 contribution
- `ESI`: about +$12.89 contribution

Net swap improvement: about +$250.41.

## Interpretation

The current market-intelligence layer is most useful as a regime/risk filter:

- penalize candidates with regime-break risk
- penalize broken price action
- penalize negative idiosyncratic news pressure
- allow or modestly boost cleaner opportunities

It is not yet reliable as a pure top-5 winner selector.

## ML Calibration Status

First-pass calibration was trained on only 73 rows.

The ML-calibrated scorer improved baseline but underperformed the heuristic NLP layer:

- Baseline top-20 10d PnL on $10,000: +$87.06
- Heuristic NLP top-20 10d PnL: +$337.47
- ML-calibrated top-20 10d PnL: +$133.02

Reason:

The ML model does not yet have enough examples. It under-penalized bad candidates such as `AMBA` and `TRMB`.

Decision:

- Keep heuristic NLP adjustment as the active candidate.
- Treat ML calibration as diagnostic until historical point-in-time news/event data exists.

## Next Build Step

Build a point-in-time historical news/event archive:

1. Collect historical articles/events by ticker/date.
2. Store raw source documents with `published_at`, source, title, URL, and text.
3. Extract semantic events using FinBERT and semantic classifier.
4. Aggregate rolling event features by ticker/date without future leakage.
5. Join event features to historical signal dates.
6. Train ML weights on many months/years of signal outcomes.
