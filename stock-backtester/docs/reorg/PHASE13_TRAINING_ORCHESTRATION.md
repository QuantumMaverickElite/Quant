# Phase 13: training orchestration

The historical intelligence training commands remain stable user-facing
entry points. Shared, dependency-light mechanics now live in
`src/backtester/intelligence/training_orchestration.py`:

- child-step execution and fail-fast/keep-going behavior;
- four-column manifest writing;
- filename-safe float formatting;
- shell command quoting and input-path filtering.

Batch, pool, and long-run runners retain their own defaults, research policy,
child command paths, and `outputs/intelligence/training_runs/` contracts.
`monitor_intelligence_training.py` remains a presentation-oriented command.
No training was executed and no baseline authority was changed.
