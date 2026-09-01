# Reorg V1 final state

**Freeze audit date:** 2026-09-01  
**Audit branch:** `reorg/phase27-final-freeze-audit`  
**Starting revision:** `99224e7`  
**Decision:** `READY_TO_FREEZE`

Reorg V1 makes the project easier to navigate without choosing research
winners or merging methods that behave differently. Older results do not all
have complete provenance, but they remain available for inspection.

## Ten-minute map

From the repository root, `README.md` identifies:

- `stock-backtester/` as the active research/backtesting system;
- `archive/` as stored copies of historical intelligence overlays, not runtime code;
- `worker_ingest/` as the directory used to exchange worker results;
- `dividend-capture/` as the old output path retained for dividend experiments;
- `.venv/` and `.codex/` as local environment and tooling directories.

Within `stock-backtester/`:

| Path | What belongs there |
| --- | --- |
| `src/backtester/` | Reusable implementation and typed interfaces |
| `scripts/` | Stable commands, orchestration, compatibility wrappers, and legitimate command-heavy programs |
| `research/` | Experiments, ablations, controls, diagnostics, and historical research runners |
| `tests/` | Deterministic offline contracts and regressions |
| `tools/` | Repository maintenance and archive-verification tools |
| `docs/` | Current guides plus clearly separated history and investigation notes |
| `configs/` | Repository policies and metadata/config declarations |
| `outputs/` | Ignored generated files, including files passed between pipeline stages |
| `rust_engine/` | Separate Rust stress/acceleration regime |

Current entry points are `README.md`, `docs/README.md`,
`docs/architecture.md`, `docs/research_workflow.md`,
`docs/large_universe_pipeline.md`, and `docs/output_policy.md`. Phase records
record how the repository changed; use the current guides for day-to-day work.

## Current and historical intelligence work

- Event learning is the current intelligence research direction. It does not
  allocate portfolios directly.
- `MarketIntelligenceEngine` and related provider/evidence/scoring paths are a
  still-wired operational fallback.
- `backtester.intelligence.ml_policy` and its command wrappers remain for older
  ML-policy experiments.
- The 66 archived overlay generations are stored for inspection and recovery,
  not used as runtime code.
- Allocator-facing MarketState, fast-volatility feature construction, and
  historical GARCH portfolio mechanics have distinct package owners.
- Package/tabular, staged cached, and one-pass cached peer/spread regimes remain
  distinct and are not established as equivalent.
- Historical dividend research has four separate generations under
  `research/dividend_capture/`; none is the current production strategy.

## Older work and generated files

- `archive/intelligence_overlays/` contains 66 byte-verified generations and
  289 payload files (291 tracked files including two READMEs).
- Versioned intelligence history is under `docs/history/intelligence/`.
- Reorganization records remain under `docs/reorg/` behind a history index.
- `dividend-capture/outputs/` retains 60 ignored historical artifacts at its
  documented compatibility path.
- `worker_ingest/` remains ignored at repository root because two parsers read
  its exact Chromebook path.

## Outputs

Phase 26 records 34 stock-backtester output families plus the dividend lane in
`PHASE26_OUTPUT_INVENTORY.csv`. Each major family is classified as a pipeline
input, cache, report, research result, training artifact, stress output,
temporary file, or external interface. Keeping a result does not make it the
preferred baseline.

New significant runs should follow `docs/output_policy.md`: use a shallow
family/run layout, write a small manifest with revision, command/config, seed,
universe/date range, inputs, schemas, and baseline status, and keep caches and
temporary files clearly separate from research results.

## Known follow-up work

These issues remain after Reorg V1, but they do not prevent normal development:

1. The project has not chosen H20 or H100 as the default baseline.
2. The preferred threshold implementation among Fast V2, Fast V3,
   feature-matrix, and matrix-engine variants
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
   documented baseline decision.
8. Retention automation is not implemented; policy exists, and deletion still
   requires run-level evidence.
9. The root dividend output directory remains because old experiments use it;
   `worker_ingest/` remains because parsers use its exact path.
10. A future native C/operator console is outside Reorg V1; no implementation
    exists and the experiment registry does not imply one.

## Adding new research

For a new correlation + mean-reversion + Monte Carlo hypothesis:

1. Put reusable correlation/signal/backtest mechanics in the corresponding
   existing package under `src/backtester/` only when genuinely reusable.
2. Put the experiment under `research/correlation/` when correlation is the
   primary question, or `research/mean_reversion/` when portfolio/signal policy
   is primary; do not create a new lane for one program.
3. Add typed discovery/config metadata to `backtester.experiments` when useful;
   the CLI or research program still defines how the experiment runs.
4. Add a deterministic test only for stable reusable behavior or compatibility,
   not for the research result itself.
5. Write run artifacts under
   `outputs/experiments/<experiment_name>/<run_id>/` with a manifest.
6. Document the question, baseline, control, ablation, leakage checks, result,
   and whether it should replace an existing baseline in the relevant research
   README or result note.
7. Compare against a same-universe baseline and record horizon, seed, and input
   identity without treating H20 or H100 as the default.

## Ten-minute re-entry score

| Dimension | Score (1–5) | Finding |
| --- | ---: | --- |
| Navigation | 5 | Root and project maps reach all requested surfaces in at most two hops |
| Ownership | 5 | Source, commands, research, tests, tools, docs, and outputs have clear roles |
| Current vs history | 5 | Intelligence, overlays, reorg history, and operational fallback are visibly separated |
| Command discoverability | 4 | 136 direct Python commands remain, but the command README and inventories classify them |
| Research discoverability | 5 | Six named research lanes have scoped READMEs and current workflow guidance |
| Output discoverability | 4 | Every major family is classified; run-level promotion remains incomplete |
| Testability | 4 | Major extracted boundaries have deterministic contracts; optional dependencies skip in minimal environments |
| Reproducibility | 3 | New-run policy is clear, but historical output provenance is often weak; acceptable known limitation |
| Extensibility | 4 | New implementation, experiment, test, registry, output, and documentation homes are explicit |

The only score below four is historical reproducibility. That limitation is
documented: older artifacts and unresolved choices remain available, important
file contracts are recorded, and new runs have a provenance policy. It does not
prevent navigation or operation.

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

The dependency-complete numerical, import, and `--help` checks still need to run
in the project's real environment before this record is committed. The managed
environment lacks NumPy and Pandas, so it could not run those checks.

## Starting point after freeze

Begin with the project README and research workflow. Future work should address
a specific hypothesis, method, operational need, or maintenance task rather
than reopening broad repository reorganization.
