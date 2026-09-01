# Intelligence

The intelligence subsystem contains three approaches. They share some data and
commands, but they are not interchangeable and none is the portfolio allocator.

## Which approach to use

| Approach | Status | Code |
| --- | --- | --- |
| Event learning | Current research direction; does not allocate portfolios directly | `events/`, `llm/`, `features/`, `calibration/`; evaluation under `research/event_learning/` |
| Heuristic intelligence | Still-wired operational fallback | package-root engine, providers, evidence graph, scoring, reporting, and signal integration |
| ML policy | Historical research tooling | `ml_policy/` with compatibility commands under `scripts/` |

## Event-learning implementation

- `events/` owns event schemas, fact construction, time-safe outcome labels,
  impact datasets, event-day aggregation, and event features.
- `llm/` owns contextual extraction, structured classification, semantic
  processing, joins, and NLP runtime.
- `features/` owns historical news/sentiment transformations and panel
  construction.
- `calibration/` owns calibration datasets, fitted weights, and walk-forward
  calibration.

The required causal boundary is `event_time <= signal_time`. LLM output is
structured research context and must not directly control allocation.
Evaluation and benchmark programs live under
[`research/event_learning/evaluation/`](../../../research/event_learning/evaluation/README.md).

## Operational heuristic fallback

`intelligence_engine.py` and the related source loading, claim/evidence
extraction, price-risk scoring, opportunity/regime scoring, reporting, and
signal integration are still wired into operational commands. Provider and
ingestion files remain at the package root because worker bundles and existing
imports use those exact paths.

Start with [the operational engine note](../../../docs/market_intelligence_engine.md).
Legacy standalone scorers are documented under
[`scripts/legacy/intelligence_heuristics/`](../../../scripts/legacy/intelligence_heuristics/README.md).

## Historical ML-policy research

The [ML-policy package](ml_policy/README.md) contains reusable mechanics for
older application, validation, sweep, and permutation studies. Its commands
remain under `scripts/` so earlier experiments still run. It is not part of
the current event-learning approach and does not allocate portfolios.
Versioned research documentation is indexed under
[`docs/history/intelligence/`](../../../docs/history/intelligence/README.md).

## Providers, workers, and training

Provider and source-acquisition modules remain near the package root. Worker
scripts package these modules and read results from exact paths under the root
`worker_ingest/` directory, so moving them requires updating and testing that
workflow as a whole.

Historical training commands remain user-facing under `scripts/`. Shared
manifest writing and child-step launching live in
`training_orchestration.py`. Batch, pool, and detached long-run modes remain
separate. Their presence does not identify one run as the preferred baseline.

## Inputs, outputs, validation

Typical inputs are provider/worker payloads, event facts, prices, labels, and
saved training tables. Outputs live under `outputs/intelligence/` and mix
datasets, audit reports, classifications, calibration artifacts, and training
runs. See [output policy](../../../docs/output_policy.md).

Relevant offline tests include event/reorganization contracts, ML-policy family
tests, training-orchestration tests, and table-I/O tests under `tests/`.
Provider/network workflows require separate controlled validation.
