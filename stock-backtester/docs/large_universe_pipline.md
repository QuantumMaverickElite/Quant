# Large-Universe Research Pipeline

This document records the work that moved the project from a small, mostly hand-picked mean-reversion research universe toward a scalable market-wide research pipeline.

The goal is to support a future semi-allocator that can scan thousands of stocks, find correlated peer relationships, detect relative dislocations, generate candidate trades, and stress test those trades with the Rust engine.

---

## 1. Why This Was Needed

The earlier mean-reversion pipeline worked, but it had a major limitation: actual strategy orders still came from an existing signal file built from a small universe. Expanding the universe only changed random controls. It did not make the strategy select trades from the whole market.

That means the Rust stress engine could test whether existing orders beat random replacements, but it was not yet a full-market signal generator.

The new architecture creates reusable market-scale inputs:

```text
universe builder
    ↓
price matrix
    ↓
returns matrix
    ↓
peer search
    ↓
peer-basket spread generation
    ↓
large-universe signals
    ↓
context adjustment
    ↓
Rust stress engine
```

---

## 2. Universe Builder

The universe builder is:

```text
scripts/build_universe.py
```

It supports:

```text
market
exchange
random / sampled-market
file
```

The first broad market universes included thousands of tickers, but also many securities that are not useful for common-stock peer research, including ETFs, ETNs, closed-end funds, preferreds, notes, warrants, rights, units, trust products, and fund-like tickers.

This polluted early peer-search results. Some technology stocks were getting fund-like peers instead of actual operating-company peers.

The builder was improved with stricter filtering:

```text
--common-only-ish
--common-stock-only
```

The stricter `--common-stock-only` mode removes obvious non-common-stock instruments by name and ticker heuristics. It also includes a hard blacklist for fund-like tickers that survived metadata filtering.

The final verified v3 universe was:

```text
/tmp/quant_universes/us_market_common_stock_only_v3.txt
```

It had:

```text
4,260 tickers before price-history filtering
```

The contamination watchlist check returned:

```text
clean
```

The checked watchlist included:

```text
ETO
CET
HQH
HQL
ASA
TY
SOR
GLU
```

---

## 3. Price Matrix Export

The price matrix exporter is:

```text
scripts/export_rust_matrix_inputs.py
```

It exports:

```text
prices.bin
prices_meta.json
orders.csv
download_report.csv
price_filter_report.csv
```

This script was upgraded because full-market downloads through `yfinance` can fail or become rate-limited. A broken export previously dropped important signal tickers and reduced the exported strategy orders, which made the strategy result invalid.

The exporter now supports:

```text
chunked downloads
configurable batch size
sleep between batches
retry logic
signal ticker prioritization
signal ticker protection
post-download price-history filtering
metadata summaries
order-count sanity checks
```

Important rule:

```text
Never trust a full-market export unless the actual strategy orders are preserved.
```

The final v3 common-stock-only export preserved:

```text
490 orders
25 order tickers
2,739 clean price columns
2,113 price rows
22.08 MB binary price matrix
```

This means the strategy was not damaged by missing price data.

---

## 4. Returns Matrix Export

The returns matrix exporter is:

```text
scripts/export_returns_matrix.py
```

It converts the binary price matrix into:

```text
returns.bin
returns_meta.json
return_filter_report.csv
```

It supports:

```text
simple returns
log returns
return-column filtering
extreme return clipping
optional NaN-to-zero replacement
```

Extreme return clipping was added because early raw returns had unrealistic one-day jumps, likely from corporate actions, bad adjusted prices, or unusual securities.

The current research export uses clipped log returns:

```text
--return-type log
--clip-returns
--max-abs-return 1.0
```

The final v3 returns matrix had:

```text
2,112 rows × 2,739 tickers
finite rate about 99.71%
510 clipped return values
max absolute return 1.0
22.07 MB binary returns matrix
```

The row count is expected because returns lose one row relative to prices.

---

## 5. Large-Universe Peer Search

The peer-search script is:

```text
scripts/large_universe_peer_search.py
```

It reads the returns matrix and computes top correlated peers for every ticker using a trailing return window.

Current configuration:

```text
window: 252 trading days
top_k: 10 peers
min_overlap: 200 observations
positive correlations only
block_size: 512
```

The script uses blockwise matrix multiplication, so it searches thousands of tickers very quickly.

The final v3 peer search produced:

```text
2,739 tickers
27,390 peer rows
about 1 second wall time
watchlist contamination: clean
```

Example peer sets:

```text
NVDA:
TSM, NVMI, AVGO, FN, VRT, KLAC, LRCX, AMD, JBL, FLEX

JPM:
BAC, C, GS, WFC, MS, COF, USB, TFC, CFG, SYF

XOM:
CVX, COP, EOG, DVN, MGY, OVV, CHRD, OXY, FANG, CVE

AAL:
DAL, ALGT, ALK, LUV, CCL, NCLH, LIND, BC, H, PK
```

AAPL, META, and GOOGL still have less obvious peer sets. That may not be contamination. It may mean their top correlations are weaker or more factor-driven in the selected 252-day window. Later signal generation should include peer-quality thresholds.

---

## 6. Rust Stress Engine Status

The Rust stress engine is no longer the main bottleneck.

Earlier full-market stress tests showed that Rust/Rayon can handle large Monte Carlo workloads efficiently. The engine handled hundreds of thousands of simulations across a clean market replacement universe while preserving compact output.

Current interpretation:

```text
Rust compute: strong
binary matrix format: strong
Monte Carlo stress engine: strong
data ingestion: slower and more fragile
large-universe signal generation: next major bottleneck
```

Python should continue handling orchestration, export, and reporting. Rust should handle repeated simulation, stress testing, and eventually other performance-critical loops.

---

## 7. Important Debugging Lessons

### 7.1 Larger universe does not mean larger allocator yet

Passing a larger universe to the Rust stress engine does not automatically change the actual strategy. The actual orders still come from the signal file.

A larger universe currently affects random controls, not actual signal generation.

A real large-universe allocator requires:

```text
large-universe signal generation
peer-basket spread generation
candidate ranking
portfolio construction
stress testing
```

### 7.2 Preserve order count

If a full-market export drops actual signal tickers, exported orders can collapse. That creates a damaged strategy test.

Current sanity check:

```text
expected current order count: 490
expected current order tickers: 25
```

If the exported order count is much lower, do not trust the result.

### 7.3 Clean the universe before expensive downloads

Peer search exposed fund-like contamination. The correct debugging method was:

```text
1. inspect suspicious peer names
2. grep the universe file
3. confirm bad tickers existed before download
4. patch build_universe.py
5. rebuild universe
6. grep again before downloading
```

This avoided wasting time on repeated full-market exports.

### 7.4 Peer search is fast enough

The peer-search computation over thousands of tickers completed in about one second. The next challenge is not correlation speed. It is turning peer maps into useful rolling signals.

---

## 8. Current Valid Pipeline

The current valid market-scale research pipeline is:

```bash
python scripts/build_universe.py \
  --mode market \
  --exclude-etfs \
  --common-stock-only \
  --out /tmp/quant_universes/us_market_common_stock_only_v3.txt

python scripts/export_rust_matrix_inputs.py \
  --signals outputs/signals/mean_reversion_signals_context_adjusted.parquet \
  --out-dir /tmp/quant_rust_matrix/h100_market_common_stock_only_v3 \
  --start 2018-01-01 \
  --signal-horizon 100 \
  --hold-days 100 \
  --min-adjusted-confidence 0.10 \
  --top-n-per-date 5 \
  --universe-file /tmp/quant_universes/us_market_common_stock_only_v3.txt \
  --dtype float32 \
  --drop-bad-price-columns \
  --min-valid-price-coverage 0.80 \
  --download-batch-size 400 \
  --download-sleep-seconds 1 \
  --download-retries 2

python scripts/export_returns_matrix.py \
  --prices-meta /tmp/quant_rust_matrix/h100_market_common_stock_only_v3/prices_meta.json \
  --out-dir /tmp/quant_returns/h100_market_common_stock_only_v3_clipped \
  --return-type log \
  --dtype float32 \
  --drop-bad-return-columns \
  --min-valid-return-coverage 0.80 \
  --clip-returns \
  --max-abs-return 1.0

python scripts/large_universe_peer_search.py \
  --returns-meta /tmp/quant_returns/h100_market_common_stock_only_v3_clipped/returns_meta.json \
  --out-dir /tmp/quant_peers/h100_market_common_stock_only_v3_w252_top10 \
  --window 252 \
  --top-k 10 \
  --min-overlap 200 \
  --block-size 512 \
  --positive-only
```

Final verified temporary outputs:

```text
/tmp/quant_rust_matrix/h100_market_common_stock_only_v3
/tmp/quant_returns/h100_market_common_stock_only_v3_clipped
/tmp/quant_peers/h100_market_common_stock_only_v3_w252_top10
```

These are temporary research outputs and should not be committed unless intentionally archived.

---

## 9. Next Step: Peer-Basket Spread Generation

The next major research step is large-universe peer-basket spread generation.

We already have:

```text
ticker → top correlated peers
```

Next we need:

```text
ticker behavior - peer basket behavior
```

The peer-basket spread engine should compute:

```text
peer_basket_return
ticker_return
relative_spread
rolling_spread_mean
rolling_spread_std
peer_spread_z
direction
confidence
```

Candidate signal logic:

```text
if peer_spread_z is very negative:
    ticker may be cheap relative to peers → long candidate

if peer_spread_z is very positive:
    ticker may be expensive relative to peers → short/avoid candidate
```

This will be the first real large-universe mean-reversion signal generator.

---

## 10. Future Improvements

Potential next upgrades:

```text
peer-quality thresholds
rolling peer maps
sector/industry-aware peer filters
liquidity and dollar-volume filters
market-cap filters
exclude microcaps
exclude ADRs if needed
GPU/CuPy peer search for larger matrices
Rust implementation of peer-basket spread generation
visual peer network graphs
correlation heatmaps
regime-colored equity curves
Monte Carlo percentile bands
```

The most important near-term improvement is:

```text
large-universe peer-basket spread generation
```

That is the next step toward the semi-allocator.
