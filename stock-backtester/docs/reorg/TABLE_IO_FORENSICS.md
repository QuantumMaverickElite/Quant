# Table-I/O Forensics

This is the Phase 1 comparison used before extracting shared infrastructure.
It is intentionally limited to general CSV/Parquet table dispatch; JSONL,
binary matrices, and domain schemas remain outside this slice.

## Consolidated family

| Path | Callers / role | Accepted formats | Write semantics | Directory behavior | Decision |
|---|---|---|---|---|---|
| `src/backtester/intelligence/candidates.py` | Candidate loading and allocator-facing intelligence helpers | `.csv`, `.parquet`, `.pq` (case-insensitive) | `index=False` | Creates parent directory | Compatibility aliases now delegate to canonical utility |
| `scripts/permutation_test_ml_policy.py` | ML-policy permutation research | `.csv`, `.parquet`, `.pq` (case-insensitive) | `index=False` | Creates parent directory | Migrated |
| `scripts/validate_ml_policy_candidate.py` | ML-policy validation research | `.csv`, `.parquet`, `.pq` (case-insensitive) | `index=False` | Creates parent directory | Migrated |
| `scripts/apply_ml_policy_strength.py` | ML-policy adjustment research | `.csv`, `.parquet`, `.pq` (case-insensitive) | `index=False` | Creates parent directory | Migrated |
| `scripts/sweep_ml_policy_strength.py` | ML-policy parameter sweep research | `.csv`, `.parquet`, `.pq` (case-insensitive) | `index=False` | Creates parent directory | Migrated |

These implementations had equivalent dispatch and serialization semantics.
Their only observed difference was the unsupported-file error wording in the
permutation script (`Unsupported file type` versus `Unsupported table type`).
No caller was found to branch on that message, so the canonical error wording
is now `Unsupported table type: <path>`.

## Deliberately unmigrated families

- `build_llm_benchmark_sample.py`, `compare_llm_classification_runs.py`,
  `run_llm_classification_batch.py`, and `llm_feature_join.py` also support
  JSONL. Their format contract is broader than the canonical utility.
- Event-learning modules use a narrower `.csv`/`.parquet` contract and have
  domain-specific ownership; they were not mass-edited in this slice.
- `run_intelligence_training_batch.py`, `run_historical_intelligence_stress.py`,
  and `simulate_intelligence_equity_curves.py` have local error/format logic;
  migration can be considered after a separate compatibility review.
- Ordinary one-off `DataFrame.to_csv()`/`read_parquet()` calls were not treated
  as duplicated abstractions.

## Canonical ownership

`src/backtester/utils/tables.py` is the least disruptive location: it is inside
the existing package, has no strategy or intelligence ownership, and is usable
by both package modules and scripts already importing `backtester` components.
The API is deliberately only `read_table` and `write_table`.
