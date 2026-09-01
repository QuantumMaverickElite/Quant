# Intelligence

The intelligence subsystem contains three distinct lineages. They share some
data and commands but must not be treated as one promoted allocator.

## Authority and status

| Lineage | Status | Ownership |
| --- | --- | --- |
| Event learning | Current research direction; not allocator authority | `events/`, `llm/`, `features/`, `calibration/`; evaluation under `research/event_learning/` |
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

`intelligence_engine.py` and related source loading, claim/evidence extraction,
price-risk scoring, opportunity/regime scoring, reporting, and signal
integration remain operationally wired. Provider and ingestion files remain at
the package root because worker packaging and exact import paths are
compatibility constraints.

Start with [the operational engine note](../../../docs/market_intelligence_engine.md).
Legacy standalone scorers are documented under
[`scripts/legacy/intelligence_heuristics/`](../../../scripts/legacy/intelligence_heuristics/README.md).

## Historical ML-policy research

The [ML-policy package](ml_policy/README.md) contains reusable mechanics for
historical application, validation, sweep, and permutation studies. Its stable
historical commands remain under `scripts/`. It is not current event-learning
or allocator authority. Versioned research documentation is indexed under
[`docs/history/intelligence/`](../../../docs/history/intelligence/README.md).

## Providers, workers, and training

Provider/source acquisition modules remain near the package root. Worker
scripts and root `worker_ingest/` infrastructure have operational deployment,
bundle, and path assumptions; do not reorganize them without a dedicated
contract audit.

Historical training commands remain user-facing under `scripts/`. Shared
manifest writing and child-step launching live in
`training_orchestration.py`. Batch, pool, and detached long-run modes remain
separate; no baseline authority is inferred.

## Inputs, outputs, validation

Typical inputs are provider/worker payloads, event facts, prices, labels, and
saved training tables. Outputs live under `outputs/intelligence/` and mix
datasets, audit reports, classifications, calibration artifacts, and training
runs. See [output policy](../../../docs/output_policy.md).

Relevant offline tests include event/reorganization contracts, ML-policy family
tests, training-orchestration tests, and table-I/O tests under `tests/`.
Provider/network workflows require separate controlled validation.
