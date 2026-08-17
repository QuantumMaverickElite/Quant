# Phase 7 intelligence topology

The user-performed Phase 7 move grouped two high-confidence current-research
families:

- `intelligence/events/` — event schemas, facts, time-safe labels, impact
  datasets, event-day aggregation, and event features.
- `intelligence/llm/` — contextual extraction, semantic classification and
  clustering, LLM classification/join, and NLP runtime support.

The current research flow is:

```text
provider/source payloads
  -> normalized source rows
  -> event facts
  -> time-safe outcome labels
  -> event-impact dataset
  -> structured/LLM features
  -> event-day aggregation
  -> baseline or walk-forward learning
  -> future bounded allocator overlay
```

This remains research, not allocator authority. Historical ML-policy research
remains in `intelligence/ml_policy/`; operational heuristic/fallback intelligence
remains separate at the intelligence root.

The move reduced the intelligence root from 48 direct Python files to 35, with
`events/` and `llm/` providing two meaningful direct entries. Provider/ingestion,
learning/calibration, and operational/evaluation families are intentionally
deferred until their callers and compatibility contracts are mapped.
