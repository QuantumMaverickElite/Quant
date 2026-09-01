# Market Intelligence v3.2: SEC Historical Feature Builder

This patch adds point-in-time SEC filing features for the ML training path.

## What it adds

- `src/backtester/intelligence/historical_feature_builder.py`
- `scripts/build_historical_sec_features.py`

The builder reads SEC JSONL produced by `scripts.fetch_sec_intelligence_sources`, then creates ticker/date features such as:

- days since latest filing
- latest filing form
- filing counts over rolling windows
- weighted filing pressure over rolling windows
- per-form flags/counts for `8-K`, `10-Q`, `10-K`, `S-1`, `424B`, and `DEF 14A`

## Why this matters

The previous ML calibration only had one current evaluated slice, so it could not learn stable weights. This patch lets the system build a historical feature table from SEC filings and join it to dated signal rows without using future filings.

SEC filings are a better ticker-specific historical source than GDELT because they are:

- point-in-time
- structured by ticker/CIK
- timestamped
- less noisy than broad news discovery
- legally and operationally stable

GDELT can still be useful for broad macro and sector context, but it should not be the primary ticker-specific ML training source.

## Example

After fetching SEC records:

`python -m scripts.build_historical_sec_features --sec-sources data/intelligence/historical/raw/sec_selected_2026_05_smoke.jsonl --signals outputs/signals/mean_reversion_allocator_intelligence_v2_evaluated_labeled.parquet --features-out outputs/intelligence/historical/sec_features_2026_05_smoke.parquet --joined-out outputs/signals/mean_reversion_allocator_intelligence_with_sec_smoke.parquet --windows 1 7 30`

## Notes

- Same-date filings are treated as available on that signal date. If the strategy later moves to intraday precision, the builder should compare exact filing timestamps to the signal decision timestamp.
- Raw fetched SEC JSONL should remain local data unless deliberately adding a small fixture.
- These features are inputs for calibration; they do not trade directly by themselves.
