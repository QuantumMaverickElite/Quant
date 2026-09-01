# Event-learning research

Event learning is the current intelligence research direction. It produces
features and evaluations; it does not allocate portfolios directly.

## Scope

The event-learning path studies:

```text
source or worker payloads
  -> event facts
  -> time-safe forward outcomes
  -> event-impact datasets
  -> optional LLM classifications
  -> event-day aggregation
  -> baseline or walk-forward models
  -> allocator experiments
```

Reusable implementation belongs under
[`src/backtester/intelligence/`](../../src/backtester/intelligence/README.md).
Pipeline commands that build facts, labels, datasets, and classifier inputs
remain under `scripts/`. This directory owns research evaluation and benchmark
analysis rather than provider operations.

## Evaluation

[`evaluation/`](evaluation/README.md) contains dataset audits, deterministic LLM
benchmark sampling, and classification-run comparisons. These are
artifact-consuming research programs, not offline unit tests.

## Research constraints

- Enforce `event_time <= signal_time`.
- Do not let LLM output directly control allocation.
- Treat heuristic `MarketIntelligenceEngine` behavior as a separate
  operational fallback.
- Use `src/backtester/intelligence/ml_policy/` only for older ML-policy
  experiments.
- Promote no event feature or model without baseline, ablation, leakage, and
  reproducibility evidence.

Detailed design milestones under `docs/intelligence/` record earlier research.
Use this README and the intelligence package README to find the current code.
