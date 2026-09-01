# Authoritative Subsystem Map

Phase 0 baseline: branch `reorg/phase0-authority-inventory`, HEAD descended from `phase2/api-llm-event-classifier`. This document records current ownership hypotheses supported by tracked code, documentation, imports, and recent branch history. It does not authorize moves or behavior changes.

Machine-readable source: [subsystems.csv](subsystems.csv). The detailed script map is [SCRIPT_INVENTORY.md](SCRIPT_INVENTORY.md); output interfaces are in [OUTPUT_CONTRACTS.md](OUTPUT_CONTRACTS.md).

## Authority summary

| Subsystem | Canonical path | Status | Evidence / boundary |
|---|---|---|---|
| Shared tabular I/O | `src/backtester/utils/tables.py` | REUSABLE INFRASTRUCTURE | First Phase 1 extraction; CSV/Parquet dispatch only, with compatibility imports retained through `backtester.intelligence.candidates`. |
| ML-policy research package | `src/backtester/intelligence/ml_policy/` | ACTIVE RESEARCH / HISTORICAL | v4/v5 research tooling grouped in Phase 6; top-level script paths remain compatibility wrappers and are not event-learning or operational authority. |
| Event-learning package | `src/backtester/intelligence/events/` | ACTIVE RESEARCH | Facts, labels, impact datasets, event-day aggregation, and event features; not allocator authority. |
| LLM/event-extraction package | `src/backtester/intelligence/llm/` | ACTIVE RESEARCH | Contextual extraction, semantic classification, LLM joins, and NLP runtime; structured features only. |
| Historical intelligence features | `src/backtester/intelligence/features/` | ACTIVE RESEARCH | Historical news feature, sentiment, and panel construction downstream of source acquisition and upstream of calibration; not allocator authority. |
| Intelligence calibration | `src/backtester/intelligence/calibration/` | ACTIVE RESEARCH | Calibration dataset construction, fitted weights, and time-safe walk-forward evaluation; output schemas and paths remain unchanged. |
| Combined-signal research | `research/combined_signals/` | ACTIVE RESEARCH | Allocator ranking/comparison diagnostics across baseline, heuristic, and ML intelligence; consumes existing artifacts and owns no reusable implementation. |
| Repository navigation spine | `README.md`, subsystem `README.md` files, `docs/README.md`, `scripts/README.md` | DOCUMENTATION / TOOLING | Phase 5 entry points; descriptive only and not an execution authority. |
| Historical dividend-capture research | `research/dividend_capture/` | HISTORICAL RESEARCH | Four distinct experiment families; contract-protected and not package or allocator authority. |
| Experiment registry | `src/backtester/experiments.py` | REUSABLE INFRASTRUCTURE | Read-only typed discovery metadata for a small pilot; no execution authority. |
| Parameter/configuration registry | `src/backtester/experiments.py` (`ParameterSpec`, `ExperimentConfig`) | REUSABLE INFRASTRUCTURE | Typed defaults, provenance, modes, JSON serialization, and validation only; existing command defaults remain authoritative. |

| Subsystem | Canonical path | Status | Confidence | Migration risk |
|---|---|---|---|---|
| Packaged backtester | `src/backtester/cli.py`, `src/backtester/engines/` | ACTIVE CORE | HIGH | MEDIUM |
| Mean-reversion signals | `src/backtester/signals/mean_reversion.py` | ACTIVE CORE | HIGH | HIGH |
| Volatility/GARCH | `src/backtester/analytics/volatility.py` | ACTIVE CORE | HIGH | MEDIUM |
| Entropy | `src/backtester/analytics/entropy.py` | ACTIVE CORE | HIGH | MEDIUM |
| Market context | `src/backtester/context/`, `src/backtester/decision/` | REUSABLE INFRASTRUCTURE | HIGH | HIGH |
| Correlation/deformation | `src/backtester/correlation/` | ACTIVE RESEARCH | HIGH | HIGH |
| Large-universe pipeline | `scripts/build_universe.py`, matrix/export/peer scripts | ACTIVE RESEARCH | HIGH | HIGH |
| Matrix allocator | `src/backtester/engines/matrix_allocator_engine.py` | REUSABLE INFRASTRUCTURE | HIGH | HIGH |
| Python Monte Carlo | family-specific `scripts/monte_carlo_*.py` | ACTIVE RESEARCH | MEDIUM | MEDIUM |
| Rust stress engine | `rust_engine/src/`, `stress_mc` | REUSABLE INFRASTRUCTURE | HIGH | HIGH |
| Market fabric | `visuals/`, overlay augmentation scripts | ACTIVE RESEARCH | HIGH | HIGH |
| Operational intelligence | `src/backtester/intelligence/intelligence_engine.py` and live runner | OPERATIONAL FALLBACK | HIGH | HIGH |
| Event-learning intelligence | `src/backtester/intelligence/events/` | ACTIVE RESEARCH | HIGH | HIGH |
| NLP/LLM features | `src/backtester/intelligence/llm/` | ACTIVE RESEARCH | HIGH | HIGH |
| Training | walk-forward and event-day runners | ACTIVE RESEARCH | MEDIUM | HIGH |
| Dividend capture | `research/dividend_capture/` plus separate `src/backtester/strategies/event_strategies.py` baseline | HISTORICAL RESEARCH / ACTIVE CORE BASELINE | HIGH | MEDIUM |
| Survivable volatility | `src/features/survivable_volatility.py` | ACTIVE RESEARCH | MEDIUM | MEDIUM |
| Workers | `scripts/workers/`, local `worker_ingest/` | OPERATIONAL FALLBACK | HIGH | HIGH |
| Visualization | `visuals/`, `src/backtester/visuals/` | ACTIVE RESEARCH | HIGH | MEDIUM |

## Authority boundaries

- “Canonical” means current source location, not necessarily production-ready or scientifically validated.
- The operational heuristic intelligence path remains protected because it is still exported and listed in `configs/sacred_scripts.json`.
- Event-learning/LLM work is the current research direction on this branch, not a replacement for operational intelligence.
- Matrix-oriented Python/Rust workflows and package-oriented Python workflows are intentionally recorded as coexisting systems.
- No subsystem is classified obsolete from version naming alone.

## User decision required

- Confirm whether the operational heuristic intelligence path is still actively used.
- Confirm whether remote Chromebook/SSH worker conventions are permanent compatibility requirements.
