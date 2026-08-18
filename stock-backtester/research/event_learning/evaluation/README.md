# Event-learning evaluation

These programs inspect real research artifacts and produce reproducible
evaluation evidence. They are research utilities, not unit tests or core
event-pipeline commands.

## Dataset audits

- `audit_event_impact_dataset.py` checks structure, duplicates, targets, and
  leakage diagnostics for the event-impact dataset.
- `audit_event_day_impact_dataset.py` performs the corresponding event-day
  aggregation and leakage checks.

## Benchmark construction

- `build_llm_benchmark_sample.py` deterministically selects a capped benchmark
  sample for classifier evaluation.

## Classification comparison

- `compare_llm_classification_runs.py` joins two classifier runs and reports
  categorical agreement and numeric differences.

Outputs remain under `outputs/intelligence/`; moving these programs does not
move or redefine those artifact contracts.
