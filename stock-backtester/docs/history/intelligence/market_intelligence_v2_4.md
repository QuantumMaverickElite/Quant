# Market Intelligence v2.4

This patch adds allocator comparison diagnostics.

## What changed

- `diagnose_allocator_intelligence.py` now supports `--unique-tickers`.
- New `compare_allocator_intelligence.py` runs top-N comparison grids.
- Comparisons include:
  - pre-intelligence average forward return
  - post-intelligence average forward return
  - return delta
  - hit rate
  - average forward drawdown
  - worst drawdown where available
  - overlap/entered/dropped ticker counts

## Why this matters

The first v2.3 test showed a strong top-20 10-day lift on one live signal date,
but one top-N setting is not enough. This script checks whether the effect
persists across multiple portfolio sizes and horizons.

Use unique-ticker mode by default when evaluating live allocator candidates,
because a signal file can contain multiple rows for the same ticker.
