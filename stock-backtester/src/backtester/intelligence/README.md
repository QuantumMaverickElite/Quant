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
- **Operational/evaluation:** remaining allocator-facing and heuristic/fallback
  modules stay at this root until their compatibility contracts are mapped.
- **Provider/ingestion:** historical source collectors and provider policy stay
  at this root for now.
- **Learning/calibration:** calibration and walk-forward modules stay at this
  root for now.

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
