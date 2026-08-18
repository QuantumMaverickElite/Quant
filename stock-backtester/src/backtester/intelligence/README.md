# Intelligence

Purpose
-------

This directory contains three intentionally distinct lines of work. They share
some schemas and artifacts, but they are not interchangeable authorities.

Current implementation and authority
-------------------------------------

- **Operational heuristic/fallback:** `intelligence_engine.py`,
  `allocator_adjustment.py`, and related scoring modules. This is the legacy
  allocator-facing path; its operational status remains a user decision.
- **Historical ML-policy research:** [`ml_policy/`](ml_policy/) contains common
  logic plus application, validation, sweep, and permutation modules. The old
  commands remain in `scripts/` as wrappers;
  this line is research tooling, not current event-learning authority.
- **Events:** [`events/`](events/) contains event schemas/facts, time-safe
  outcome labels, impact datasets, event-day aggregation, and event features.
- **LLM / event extraction:** [`llm/`](llm/) contains contextual extraction,
  semantic classification/clustering, LLM classification joins, and NLP
  runtime support. This is the current research direction, not automatically an
  allocator replacement.
- **Features:** [`features/`](features/) contains historical news feature
  construction, sentiment transformation, and historical research-panel
  construction. It is downstream of source acquisition and upstream of
  calibration/training; it is distinct from `events/` and `llm/`, and is not
  allocator authority.
- **Calibration:** [`calibration/`](calibration/) contains calibration-dataset
  construction, fitted intelligence weights, and time-safe walk-forward
  calibration/evaluation. It consumes feature tables and produces research
  artifacts; it is not allocator authority.
- **Training orchestration:** `training_orchestration.py` contains the small
  shared mechanics used by the batch, pool, and long-run training commands.
  It does not choose research policy or execute training on import.
- **Operational/evaluation:** remaining allocator-facing and heuristic/fallback
  modules stay at this root until their compatibility contracts are mapped.
- **Provider/ingestion:** historical source collectors and provider policy stay
  at this root for now.
- **SEC historical features:** `historical_feature_builder.py` remains at this
  root as the SEC-specific point-in-time feature builder; it is separate from
  calibration and from the news-oriented `features/` family.

Connects to
-----------

Scripts build news/source features and intelligence artifacts, while signal and
allocator experiments consume selected outputs. See the output contracts before
moving any path.

Important commands
------------------

- `scripts/run_market_intelligence_live.py` (operational/live assumptions)
- `scripts/run_market_intelligence_batch.py` (batch research)
- `scripts/validate_ml_policy_candidate.py` (historical ML-policy wrapper)
- `scripts/check_intelligence_nlp.py` (bounded check where dependencies permit)
- `scripts/run_intelligence_training_batch.py`,
  `scripts/run_pool_intelligence_training.py`, and
  `scripts/launch_long_intelligence_training.py` (historical training commands)

Tests
-----

`tests/test_ml_policy_family.py` is an offline contract test. Other
intelligence checks may require data or providers; do not infer current
authority from versioned filenames.

The ML-policy files are now grouped in the compact `intelligence/ml_policy/`
subpackage. The four historical command wrappers remain the compatibility
boundary.

Current event-learning flow
---------------------------

provider/source payloads → normalized source rows → `events/event_fact_table.py`
→ time-safe outcome labels → event-impact dataset → structured/LLM event
features → event-day aggregation → baseline or walk-forward learning → future
bounded allocator overlay. The pipeline is research-only and is not promoted to
allocator authority.

See also
--------

- [`docs/intelligence/event_learning_rearchitecture.md`](../../../docs/intelligence/event_learning_rearchitecture.md)
- [`docs/reorg/ML_POLICY_SCRIPT_FAMILY.md`](../../../docs/reorg/ML_POLICY_SCRIPT_FAMILY.md)
