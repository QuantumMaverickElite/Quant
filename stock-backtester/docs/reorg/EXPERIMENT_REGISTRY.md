# Experiment Registry / Control-Plane Foundation

Phase 3 adds a read-only, typed registry at
`src/backtester/experiments.py`. It is metadata, not an execution engine.

## Concepts

- **Component**: reusable implementation capability.
- **Pipeline**: multi-stage workflow connecting components and commands.
- **Experiment**: a named research question/configuration with authority and
  reproducibility metadata.
- **Command**: an existing executable entry point, retained as a compatibility
  path.

The serialized boundary is deterministic JSON. A future CLI or native C
operator console can consume it without importing Python internals.

## Discovery

From `stock-backtester/`:

```bash
PYTHONPATH=src python -m backtester.experiments list
PYTHONPATH=src python -m backtester.experiments describe intelligence.ml_policy.permutation
PYTHONPATH=src python -m backtester.experiments validate
PYTHONPATH=src python -m backtester.experiments list --json
```

The registry does not implement `plan`, `run`, stress execution, process
orchestration, or UI integration.

## Pilot scope

The pilot registers the four historical ML-policy research experiments, the
historical ML-policy pipeline, the documented peer-spread mean-reversion
baseline, a large-universe mean-reversion pipeline, and a deformation-weighted
research entry. It does not infer authority for H20/H100 cache variants.

ML policy is explicitly classified as historical research tooling. It is not
operational heuristic intelligence, current event-learning/LLM authority, or
allocator authority.

## Adding research

No new experiment is integrated until it has an owner/subsystem, purpose,
documented inputs and outputs, parameters, a command or runner, and a test or
baseline reference where applicable. Add a typed registry entry and keep
uncertainty explicit instead of inventing defaults.
