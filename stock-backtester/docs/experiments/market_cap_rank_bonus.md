# Market-Cap Rank Bonus Experiment

## Purpose

This experiment tested whether company size can improve the existing broad-universe mean-reversion selection system.

The original intuition was simple:

When two mean-reversion candidates are close in score, the larger company may deserve a small preference because large-cap companies often have deeper liquidity, stronger institutional support, better access to capital, and greater ability to survive temporary volatility.

The goal was not to create a standalone market-cap strategy.

The goal was to test whether market capitalization can improve the ranking layer after the existing signal engine has already done its work.

---

## Where This Fits in the Existing System

This experiment is not separate from the existing system.

It works on top of the already-built context-adjusted mean-reversion signal file:

```text
outputs/signals/mean_reversion_signals_market_common_stock_only_v3_context_adjusted.parquet
```

That file already includes the core components of the current strategy stack:

```text
Correlation engine
    -> builds peer baskets and top-k peer relationships

Mean-reversion engine
    -> computes peer spread, peer_spread_z, raw_score, normalized_score, and confidence

Volatility regime engine
    -> computes realized_vol, realized_vol_z, volatility_state, and volatility_weight

Entropy engine
    -> computes return_entropy, entropy_z, entropy_state, and entropy_weight

Context adjustment layer
    -> combines confidence with volatility and entropy context into adjusted_confidence

Market-cap rank bonus
    -> adds a small size-based ranking bonus after adjusted_confidence
```

So the tested structure is:

```text
final_rank_score = adjusted_confidence + market_cap_rank_bonus
```

This means market cap is not replacing mean reversion, correlation, volatility, or entropy. It is an additional ranking layer on top of the existing context-adjusted mean-reversion/correlation system.

The honest interpretation is:

```text
This is not a market-cap-only strategy.

This is a broad-universe context-adjusted mean-reversion strategy with an added market-cap ranking bonus.
```

---

## Why Market Cap Might Help

The intuition is that size may act as a stability and survivability proxy.

Large companies often have:

- More liquidity
- More institutional ownership
- Better access to capital
- Better survivability during volatility shocks
- More analyst coverage
- More durable business franchises
- Lower probability of total collapse compared with fragile small-cap names

This does not mean large caps always outperform. It only means that when two candidates are already close, size may be a reasonable tie-breaker.

The desired behavior is:

```text
When two mean-reversion candidates are close, prefer the larger and more institutionally durable company.
```

The undesired behavior is:

```text
Blindly boost every large company regardless of signal quality.
```

---

## Market-Cap Tiers

The experiment used absolute market-cap tiers:

| Tier |             Market Cap Range |
| ---: | ---------------------------: |
|    0 |               less than $25B |
|    1 |                $25B to $100B |
|    2 |               $100B to $250B |
|    3 |               $250B to $500B |
|    4 |                 $500B to $1T |
|    5 | greater than or equal to $1T |

The strongest tested additive bonus used:

| Tier | Rank Bonus |
| ---: | ---------: |
|    0 |      0.000 |
|    1 |      0.000 |
|    2 |      0.000 |
|    3 |      0.020 |
|    4 |      0.040 |
|    5 |      0.060 |

This was intentionally used as a ranking bonus, not as a confidence multiplier.

---

## Tested Approaches

### 1. Survivable Volatility Adjustment

The first version combined market cap, volatility pressure, drawdown pressure, and trend quality into a survivable-volatility score.

This was too aggressive.

It changed confidence too broadly and reduced performance.

Result:

- Some defensive behavior appeared
- Some drawdown improvement appeared
- Final equity was worse
- Sharpe-like score was worse
- Monte Carlo percentiles were worse

Conclusion:

```text
Survivable volatility is useful as a diagnostic concept, but the first confidence-multiplier version was too heavy-handed.
```

---

### 2. Survivable Volatility Penalty-Only Version

The next version only penalized weaker names or broken-trend situations while allowing only a tiny dip-buy bonus.

This reduced drawdown slightly, but also reduced final equity and Sharpe-like performance.

Conclusion:

```text
Penalty-only survivable volatility was safer than the full boost, but it removed too much useful exposure.
```

---

### 3. Market-Cap Multiplier

The next version removed volatility and trend logic entirely and tested a simple market-cap-based confidence multiplier.

This avoided handpicked ticker bias by fetching market caps from the signal universe and assigning valuation tiers.

In the small 26-ticker universe, this did not improve performance.

Conclusion:

```text
Market cap should not be used as a universal confidence multiplier.
```

---

### 4. Market-Cap Threshold-Safe Tie-Breaker

The next version applied a threshold-safe tie-breaker.

It only boosted names that already passed the original confidence threshold and prevented below-threshold rows from crossing into the trade set because of market cap alone.

On the 26-ticker universe, this changed zero selected orders.

Conclusion:

```text
The small universe was too rigid and already biased toward large durable companies. Market cap had no room to improve selection.
```

---

### 5. Market-Cap Additive Rank Bonus

The final useful version treated market cap as an additive rank bonus:

```text
rank_score = adjusted_confidence + market_cap_rank_bonus
```

This made market cap a ranking feature rather than a broad confidence multiplier.

This version failed to help the small 26-ticker universe, but improved the broad common-stock universe.

---

## Small-Universe Result

The small-universe test used the 26-ticker H=100 mean-reversion universe.

Even the strong rank-bonus version only changed 3 added and 3 removed orders.

Added:

```text
2023-02-24  LLY
2023-03-10  JNJ
2025-09-15  WMT
```

Removed:

```text
2023-02-24  JNJ
2023-03-10  BAC
2025-09-15  COP
```

Performance was slightly worse than the baseline.

Conclusion:

```text
Market-cap rank bonus is not useful in the small 26-name universe.
```

Reason:

```text
The small universe is already mostly large-cap and high-quality, so the feature has little room to add information.
```

---

## Broad-Universe Setup

The broad-universe test used:

```text
outputs/signals/mean_reversion_signals_market_common_stock_only_v3_context_adjusted.parquet
```

Signal summary:

```text
Rows:           63,530
Unique tickers: 2,737
Date range:     2019-03-29 to 2026-05-28
Horizons:       20 and 100
```

The relevant H=100 candidate set was much larger than the small universe.

Initial eligible set:

```text
Original eligible rows:   19,797
Original unique tickers:   2,601
```

Fetching market caps for every ticker was too slow and unnecessary, so a candidate-only market-cap cache was built.

The candidate filter selected names close enough to the daily fifth-ranked candidate that a maximum rank bonus of 0.060 could matter.

Candidate filter result:

```text
Candidate rows:            1,762
Candidate unique tickers:    812
```

Market-cap cache result:

```text
Rows:                812
Missing market caps:   2
```

This made the broad-universe test practical.

---

## Broad-Universe Selection Impact

Applying the strong market-cap rank bonus to the broad universe changed selection meaningfully but not excessively.

Top-5 selection comparison:

```text
Base top orders: 897
New top orders:  897
Added:            11
Removed:          11
Changed total:    22
```

Added tickers:

```text
BAC     3
AVGO    2
XOM     1
PG      1
LRCX    1
NVDA    1
HD      1
MSFT    1
```

Removed tickers:

```text
CINF    1
BP      1
ONB     1
PRU     1
SBSI    1
FHN     1
MO      1
NSC     1
EL      1
PWR     1
VICI    1
```

Added market-cap tiers:

```text
Tier 3: 6
Tier 4: 1
Tier 5: 4
```

Interpretation:

```text
The rank bonus behaved as intended. It tilted close decisions toward larger, more liquid, more institutionally durable companies without completely changing the strategy.
```

---

## Broad-Universe Rust Stress Test

The strong market-cap rank-bonus version was tested with the Rust realistic daily portfolio stress engine.

Run:

```text
h100_market_common_stock_only_v3_market_cap_rank_bonus_strong_100k
```

Setup:

```text
Orders:              847
Price dates:         1870
Universe tickers:    2860
Runs per control:    100000
Initial capital:     10000
Max gross exposure:  1.00
Target new basket:   0.200
Max position weight: 0.100
Fee bps one-way:     5.00
```

Actual portfolio result:

```text
Final equity:   $36,261.28
Total return:   2.6261
Max drawdown:  -41.76%
Win rate:       50.64%
Sharpe-like:    0.7913
```

Monte Carlo controls:

```text
Random dates / random tickers:
  Probability random beats actual: 18.60%
  Actual percentile:               81.40%
  MC median:                       1.22x
  MC p95:                          5.34x

Same dates / random tickers:
  Probability random beats actual: 11.11%
  Actual percentile:               88.89%
  MC median:                       1.21x
  MC p95:                          3.76x
```

---

## Broad Baseline vs Market-Cap Rank Bonus

Baseline:

```text
Run:                  h100_market_common_stock_only_v3_clean_finaldate_context_adjusted_baseline_100k
Closed trades:        511
Closed trade tickers: 315
Final equity:         $36,130.50
Return:               2.61x
Max drawdown:        -42.18%
Win rate:             45.09%
Sharpe-like:          0.7424
Same-date percentile: 83.97%
Same-date beats:      16.04%
Random-date percentile: 74.82%
Random-date beats:      25.18%
```

Market-cap rank bonus:

```text
Run:                  h100_market_common_stock_only_v3_market_cap_rank_bonus_strong_100k
Closed trades:        511
Closed trade tickers: 313
Final equity:         $36,261.28
Return:               2.63x
Max drawdown:        -41.76%
Win rate:             50.64%
Sharpe-like:          0.7913
Same-date percentile: 88.89%
Same-date beats:      11.11%
Random-date percentile: 81.40%
Random-date beats:      18.60%
```

Performance delta:

| Metric                 |   Baseline | Market-Cap Rank Bonus | Direction |
| ---------------------- | ---------: | --------------------: | --------- |
| Final equity           | $36,130.50 |            $36,261.28 | Improved  |
| Return                 |      2.61x |                 2.63x | Improved  |
| Max drawdown           |    -42.18% |               -41.76% | Improved  |
| Win rate               |     45.09% |                50.64% | Improved  |
| Sharpe-like            |     0.7424 |                0.7913 | Improved  |
| Same-date percentile   |     83.97% |                88.89% | Improved  |
| Random-date percentile |     74.82% |                81.40% | Improved  |

---

## Main Conclusion

Market cap did not help in the small 26-ticker universe, but it did help in the broad common-stock universe.

The useful rule is not:

```text
Large caps always deserve higher confidence.
```

The useful rule is:

```text
When multiple mean-reversion candidates are already close, prefer the larger, more institutionally durable company.
```

Therefore, market cap should be treated as an additive ranking feature in broad-universe selection, not as a universal confidence multiplier.

Recommended interpretation:

```text
final_rank_score = adjusted_confidence + market_cap_rank_bonus
```

where the rank bonus is small and only applies to sufficiently qualified candidates.

---

## Current Best Interpretation

The market-cap rank bonus is a useful stability/ranking feature for broad-universe mean reversion.

It improved trade quality more than raw final equity.

The most important improvements were:

- Higher win rate
- Higher Sharpe-like score
- Better drawdown
- Better same-date Monte Carlo percentile
- Better random-date Monte Carlo percentile

This suggests market cap is useful as a selection-quality improvement, not necessarily as a raw return booster.

---

## Caveats

The market-cap rank-bonus run was exported with a newly downloaded price matrix, while the baseline comparison used an older clean-finaldate cached matrix.

The result is strong enough to keep the idea, but the fairest future test should reuse the exact same cached price matrix for both baseline and market-cap orders.

The market-cap cache also uses current-point-in-time market cap, not historical point-in-time market cap.

This is acceptable for a first research experiment, but production-grade testing should avoid lookahead.

Future versions should consider point-in-time or historically available proxies.

Potential future proxies:

- Historical dollar volume
- Average daily dollar volume
- Rolling liquidity tier
- Historical shares outstanding
- Price times shares outstanding when available
- Sector-relative size rank
- Index membership
- Large-cap / mid-cap / small-cap classification by date

---

## Next Steps

1. Re-export market-cap rank-bonus orders using the exact same cached price matrix as the baseline.
2. Test smaller bonus settings on the broad universe.
3. Test liquidity-adjusted rank bonus.
4. Test sector-relative market-cap rank instead of absolute market-cap tier.
5. Add the rank bonus to the allocator as an optional feature flag.
6. Keep survivable volatility as a diagnostic feature unless later tests validate it as a scoring feature.

---

## Implementation Notes

Scripts added during this experiment:

```text
scripts/build_market_cap_cache.py
scripts/create_market_cap_boost_signals.py
scripts/create_market_cap_tiebreaker_signals.py
scripts/create_market_cap_rank_bonus_signals.py
scripts/create_survivable_vol_backtest_signals.py
scripts/create_survivable_vol_penalty_only_signals.py
```

Important broad-universe generated files:

```text
outputs/tmp/market_cap_candidate_signals_h100.parquet
outputs/cache/market_caps/market_caps_market_common_stock_only_v3_h100_candidates.csv
outputs/signals/mean_reversion_signals_market_common_stock_only_v3_market_cap_rank_bonus_strong.parquet
outputs/rust_stress/h100_market_common_stock_only_v3_market_cap_rank_bonus_strong_100k
```

Recommended commit policy:

```text
Commit the scripts and documentation.
Do not commit large generated matrices or heavy parquet outputs unless they are intentionally tracked research artifacts.
```
