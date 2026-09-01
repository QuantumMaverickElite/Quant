# Reorg V1 freeze

**Freeze audit date:** 2026-09-01  
**Audit branch:** `reorg/phase27-final-freeze-audit`  
**Starting revision:** `99224e7`  
**Decision:** `READY_TO_FREEZE`

Reorg V1 establishes understandable ownership and compatibility boundaries. It
does not select research winners, unify distinct methodologies, or make every
historical artifact perfectly reproducible.

## Ten-minute map

From the repository root, `README.md` identifies:

- `stock-backtester/` as the active research/backtesting system;
- `archive/` as tracked historical preservation, never runtime authority;
- `worker_ingest/` as an intentional operational compatibility interface;
- `dividend-capture/` as ignored historical output compatibility state;
- `.venv/` and `.codex/` as local environment/tooling state.

Within `stock-backtester/`:

| Path | Frozen responsibility |
| --- | --- |
| `src/backtester/` | Reusable implementation and typed interfaces |
| `scripts/` | Stable commands, orchestration, compatibility wrappers, and legitimate command-heavy programs |
| `research/` | Experiments, ablations, controls, diagnostics, and historical research runners |
| `tests/` | Deterministic offline contracts and regressions |
| `tools/` | Repository maintenance and preservation tools |
| `docs/` | Current authority plus visibly separated history/forensics |
| `configs/` | Repository policies and metadata/config declarations |
| `outputs/` | Ignored generated state and documented filesystem contracts |
| `rust_engine/` | Separate Rust stress/acceleration regime |

Current entry points are `README.md`, `docs/README.md`,
`docs/architecture.md`, `docs/research_workflow.md`,
`docs/large_universe_pipeline.md`, and `docs/output_policy.md`. Phase records
are migration evidence, not current operating authority.

## Current authority boundaries

- Event learning is the current intelligence research direction, not allocator
  authority.
- `MarketIntelligenceEngine` and related provider/evidence/scoring paths are a
  still-wired operational fallback.
- `backtester.intelligence.ml_policy` and its stable command wrappers are
  historical ML-policy research tooling.
- The 66 archived overlay generations are preservation evidence only.
- Allocator-facing MarketState, fast-volatility feature construction, and
  historical GARCH portfolio mechanics have distinct package owners.
- Package/tabular, staged cached, and one-pass cached peer/spread regimes remain
  distinct and are not established as equivalent.
- Historical dividend research has four separate generations under
  `research/dividend_capture/`; none is package or production authority.

## Preserved history and generated state

- `archive/intelligence_overlays/` contains 66 byte-verified generations and
  289 payload files (291 tracked files including two READMEs).
- Versioned intelligence history is under `docs/history/intelligence/`.
- Reorganization forensics remain under `docs/reorg/` behind a historical
  index.
- `dividend-capture/outputs/` retains 60 ignored historical artifacts at its
  documented compatibility path.
- `worker_ingest/` remains an ignored root operational interface because two
  parsers consume its exact Chromebook path.

## Output freeze

Phase 26 records 34 stock-backtester output families plus the dividend lane in
`PHASE26_OUTPUT_INVENTORY.csv`. No major family is unknown. Pipeline contracts,
caches, reports, durable evidence, historical results, training artifacts,
stress outputs, scratch, and external interfaces are distinguished without
promoting retained artifacts as canonical.

New significant runs should follow `docs/output_policy.md`: use a shallow
family/run layout, write a small manifest with revision, command/config, seed,
universe/date range, inputs, schemas, and promotion status, and keep cache or
scratch explicitly non-authoritative.

## Explicit deferred debt

These are acceptable post-freeze concerns, not Reorg V1 blockers:

1. H20 versus H100 baseline authority remains unresolved.
2. Fast V2, Fast V3, feature-matrix, and matrix-engine threshold authority
   remains unresolved.
3. The one-pass cached peer/spread implementation remains a separate
   contract-protected script methodology.
4. Intelligence package-root direct-file grouping could be revisited only with
   provider/worker/import contracts in scope.
5. `experiments.py` and `cli.py` are large but cohesive; the registry remains
   metadata/config discovery rather than execution orchestration.
6. `strategy_scorecard.py`, historical stress/training runners, matrix/Rust
   exporters, and several MarketState commands remain large legitimate or
   compatibility-sensitive commands.
7. Historical output generations often have weak run-level provenance and no
   official promotion decision.
8. Retention automation is not implemented; policy exists, and deletion still
   requires run-level evidence.
9. The root dividend output lane and root `worker_ingest/` interface remain by
   explicit compatibility decision.
10. A future native C/operator console is outside Reorg V1; no implementation
    exists and the experiment registry does not imply one.

## Safe extension rules

For a new correlation + mean-reversion + Monte Carlo hypothesis:

1. Put reusable correlation/signal/backtest mechanics in the corresponding
   existing package under `src/backtester/` only when genuinely reusable.
2. Put the experiment under `research/correlation/` when correlation is the
   primary question, or `research/mean_reversion/` when portfolio/signal policy
   is primary; do not create a new lane for one program.
3. Add typed discovery/config metadata to `backtester.experiments` when useful;
   keep the actual CLI or research program authoritative for execution.
4. Add a deterministic test only for stable reusable behavior or compatibility,
   not for the research result itself.
5. Write run artifacts under
   `outputs/experiments/<experiment_name>/<run_id>/` with a manifest.
6. Document the question, baseline, control, ablation, leakage checks, result,
   and authority status in the owning research README or scoped result note.
7. Compare against a same-universe baseline and record horizon/seed/input
   identity without silently choosing H20 or H100 authority.

## Ten-minute re-entry score

| Dimension | Score (1–5) | Finding |
| --- | ---: | --- |
| Navigation | 5 | Root and project maps reach all requested surfaces in at most two hops |
| Ownership | 5 | Source, commands, research, tests, tools, docs, and outputs have explicit roles |
| Current vs history | 5 | Intelligence, overlays, reorg history, and fallback authority are visibly separated |
| Command discoverability | 4 | 136 direct Python commands remain, but the command README and inventories classify them |
| Research discoverability | 5 | Six named research lanes have scoped READMEs and current workflow guidance |
| Output discoverability | 4 | Every major family is classified; run-level promotion remains incomplete |
| Testability | 4 | Major extracted boundaries have deterministic contracts; optional dependencies skip in minimal environments |
| Reproducibility | 3 | New-run policy is clear, but historical output provenance is often weak; acceptable known limitation |
| Extensibility | 4 | New implementation, experiment, test, registry, output, and documentation homes are explicit |

The only score below four is historical reproducibility. It is an acceptable
known limitation because artifacts and ambiguity are preserved, current
contracts are documented, and new-run policy prevents recurrence. It is not a
navigation or operational freeze blocker.

## Validation status

The Phase 27 managed audit verified:

- all current Markdown relative links resolve;
- all 28 package initializers have resolvable internal modules and exports by
  static inspection;
- registry validation and typed config discovery pass;
- 57 offline tests pass in the managed environment, with 42 optional-dependency
  skips;
- archive verification passes with 289 payload rows, 66 generations, and the
  required aggregate hash;
- the Phase 26 inventory exactly matches 34 output families plus dividend;
- generated output, dividend output, and worker trees have zero tracked files;
- no old overlay source directory is present;
- no quantitative implementation, output, worker payload, or archive payload
  changed during the audit.

Dependency-complete numerical/import/help reruns remain the user acceptance
gate before committing this freeze record. The managed environment lacks
NumPy/Pandas; this is not evidence of a repository defect.

## Starting point after freeze

Begin with the project README and research workflow. Treat this file as the
Reorg V1 boundary: future work should be hypothesis, methodology, operational,
or maintenance work with explicit scope—not an implicit continuation of broad
physical reorganization.
