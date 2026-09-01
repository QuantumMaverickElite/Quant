# ML-Policy Script Family Migration

## Authority and purpose

The four historical commands belong to the v4/v5 ML-policy research line
documented in `docs/history/intelligence/market_intelligence_v4_4.md` through
`docs/history/intelligence/market_intelligence_v4_8.md`. They are ACTIVE RESEARCH / HISTORICAL
RESEARCH TOOLING, not operational heuristic intelligence and not the current
event-learning/LLM authority. No production allocator path was promoted.

## Migration map

| Compatibility path | Owned implementation | Role |
|---|---|---|
| `scripts/apply_ml_policy_strength.py` | `backtester.intelligence.ml_policy.application` | Apply policy strength and produce adjusted signals/audits |
| `scripts/validate_ml_policy_candidate.py` | `backtester.intelligence.ml_policy.validation` | Candidate validation and block bootstrap summaries |
| `scripts/sweep_ml_policy_strength.py` | `backtester.intelligence.ml_policy.sweep` | Strength/cap parameter sweep |
| `scripts/permutation_test_ml_policy.py` | `backtester.intelligence.ml_policy.permutation` | Within-date permutation null testing |

The top-level scripts are now thin compatibility entry points that re-export
the canonical public symbols and delegate `main()`. Existing `python -m
scripts.<name>` commands and CLI flags remain unchanged.

## Extracted shared logic

`backtester.intelligence.ml_policy.common` owns the common column-selection
helpers (`detect_col`, `detect_ticker_col`, and `detect_date_col`). Each
workflow-specific module retains its own policy formulas, bootstrap/permutation
semantics, output schemas, plotting, defaults, and random seeds.

All table reads/writes continue to use the Phase 1 utility at
`backtester.utils.tables`.

## Direct imports and compatibility

No tracked Python file was found importing symbols directly from these four
script paths. Re-exports are retained anyway because the scripts are documented
research entry points and may be used by notebooks or untracked experiments.

## Validation

- Four wrapper `--help` invocations passed offline using dependency stubs so no
  data, network, or model code ran.
- AST checks and `git diff --check` passed.
- Tiny DataFrame/numerical tests are included in
  `tests/test_ml_policy_family.py`; they are skipped when Pandas/NumPy are
  unavailable in the execution environment.
- Parent-oracle checks show the application fixture produces adjusted values
  `[0.55, 0.55]` (the cap applies to both rows), and the permutation policy
  fixture produces `[0.2, 0.2, 0.2]`. Earlier hand-written expectations of
  `[0.7, 0.55]` and `[0.3, 0.2, 0.2]` were incorrect; no implementation change
  was needed.

## Remaining debt

JSONL-capable LLM readers, event-learning readers, and other intelligence
training/stress scripts remain separate. They have broader or different table
contracts and were intentionally not migrated.
