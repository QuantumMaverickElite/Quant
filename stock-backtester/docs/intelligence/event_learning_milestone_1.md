# Event-Learning Refactor Milestone 1

## Status

Milestone 1 creates the foundation for replacing heuristic news allocation with event-impact learning.

## Completed

- Added intelligence rearchitecture documentation.
- Added storage policy documentation.
- Built event fact table from normalized worker news.
- Built time-safe forward outcome labeler.
- Fixed after-market-close leakage by shifting labels to the next tradable base date.
- Built event-level impact dataset.
- Audited duplicate pressure.
- Built ticker-day aggregate impact dataset.
- Audited ticker-day aggregate table.
- Ran tiny baseline smoke test.

## Current Outputs

- outputs/intelligence/event_fact_table.parquet
- outputs/intelligence/event_outcome_labels.parquet
- outputs/intelligence/event_impact_dataset.parquet
- outputs/intelligence/event_day_impact_dataset.parquet
- outputs/intelligence/audits/
- outputs/intelligence/baseline_reports/

## Important Results

The event-day aggregate table has:

- 110 rows
- 11 tickers
- 0 duplicate ticker/base-date rows
- 0 bad event_base_date rows

The tiny baseline model is only a smoke test.

Current sample size is too small for allocator use.

## Storage Finding

The new pipeline outputs are small.

The major storage issue is old intelligence training runs, especially large JSONL files under:

- outputs/intelligence/training_runs/multi_period_ml_research_v5
- outputs/intelligence/training_runs/multi_period_ml_research
- outputs/intelligence/training_runs/long_v5_8_api_backfill_2022_2023

## Next Steps

1. Add a storage prune/compression policy for old training runs.
2. Add full historical price source integration.
3. Add API LLM event classifier as a structured feature generator.
4. Train event-impact model on larger historical data.
5. Only after walk-forward validation, connect bounded model outputs to allocator overlay.
