# Reorganization Status Board

## Phase 0 status

Completed on `reorg/phase0-authority-inventory`:

- Existing audit policy now excludes `.vnev` as well as `.venv` and other cache/build trees.
- Import-graph audit no longer parses ignored overlays unless `--include-overlays` is explicitly requested.
- Deterministic subsystem, script, output-contract, physical-inventory, and overlay-lineage manifests were generated from bounded local evidence.
- Current architecture, authority, sacred workflows, and preservation rules are documented.
- Offline fixture tests cover role classification, overlay comparison, missing canonical destinations, and deterministic contract ordering.

## Phase 1 status

- Completed the first behavior-preserving shared-infrastructure extraction: common CSV/Parquet table I/O now lives in `src/backtester/utils/tables.py`.
- Migrated four representative ML-policy research scripts and preserved the existing `backtester.intelligence.candidates.read_table` / `write_table` import paths as compatibility aliases.
- Remaining table-I/O helpers were intentionally not mass-migrated; their semantics and ownership require separate review.

## Phase 2 status

- Completed the first script-family extraction for the historical ML-policy research line.
- The four original top-level paths remain compatibility wrappers with symbol re-exports and unchanged CLI parsers/defaults.
- Shared column detection now has one family-owned helper; workflow-specific statistical and policy logic remains separate.
- No event-learning, operational intelligence, allocator, or production behavior was changed.

## Phase 3 status

- Added a stdlib-first typed experiment/component/pipeline/command registry at `src/backtester/experiments.py`.
- Registered the four historical ML-policy experiments plus a documented mean-reversion baseline, large-universe pipeline, and deformation-weighted research entry.
- Added deterministic human-readable and JSON discovery commands: `list`, `describe`, and `validate`.
- Registry discovery is metadata-only; no experiment execution, planning, stress orchestration, or UI was added.

## Phase 4 status

- Evolved the experiment registry with typed `ParameterSpec`, `ExperimentConfig`, fixed/choice/sweep/random value models, provenance metadata, deterministic JSON, and validated in-memory overrides.
- Added read-only `config` discovery output; no experiment command is invoked and no existing CLI default was changed.
- Added stdlib-only configuration tests covering type errors, choices, sweep validation, random distribution metadata, overrides, and JSON round trips.

## Phase 5 status — repository topology

- Added a repository-root and `stock-backtester/` navigation spine with direct
  links to major subsystem homes, tests, configs, outputs, and runbooks.
- Added compact READMEs for signals, analytics, context, correlation/deformation,
  engines, intelligence, Rust, configs, and scripts.
- Added a current/research/history documentation index and a combined-signal
  research map covering baseline, context, deformation, risk, and intelligence
  adjustment layers.
- Classified the 15 historical `scripts/test_*.py` files. The five clearly
  offline control-plane/contract tests now live in `tests/`; the remaining
  data-dependent and synthetic smoke programs remain under `scripts/`.
- No production or research executable was moved, renamed, or behaviorally
  changed. Root and `stock-backtester` overlay bundles remain untouched.

## Phase 6 status — physical topology

- Five offline validation tests now live in `tests/`.
- Six repository-maintenance tools now live in `tools/reorg/`.
- The six-file historical ML-policy family now lives in
  `src/backtester/intelligence/ml_policy/`; the four historical command paths
  remain compatibility entry points.
- Tracked imports, registry metadata, output-contract references, and docs were
  repaired. No quantitative implementation or output tree changed.
- The long-term ownership decision for `dividend-capture/` is settled: it is a
  strategy/research lane within the main quant system, not a permanent root peer.
- Root overlays and `worker_ingest/` remain untouched; future ownership and
  preservation work is separate from tracked topology cleanup.

## Phase 7 status — intelligence topology

- User-performed moves grouped the current event-learning implementation under
  `src/backtester/intelligence/events/` and the LLM/event-extraction
  implementation under `src/backtester/intelligence/llm/`.
- This repair updates cross-package imports, command callers, worker packaging
  references, inventories, and documentation. No event, labeling, NLP, or LLM
  behavior changed.
- Remaining provider/ingestion, learning/calibration, and operational/evaluation
  files remain at the intelligence root for later batches.

## Phase 8 status — intelligence feature topology

- The user-performed move grouped historical news feature construction,
  sentiment transformation, and historical panel construction under
  `src/backtester/intelligence/features/`.
- Command paths remain unchanged; their imports now target the features package.
- Source acquisition/provider modules remain at the intelligence root because
  worker and path contracts have not yet been verified for movement.
- No feature, sentiment, panel, provider, or training behavior changed.

## Phase 9 status — intelligence calibration topology

- The user-performed move grouped `calibration_dataset.py`,
  `walk_forward_calibrator.py`, and `weight_calibrator.py` under
  `src/backtester/intelligence/calibration/`.
- Script imports and moved-module imports now target the calibration package.
- Existing calibration parquet, prediction/summary, and weight-calibration
  JSON paths and schemas remain unchanged.
- `historical_feature_builder.py` remains at the intelligence root as the
  SEC-specific feature builder.
- Intelligence topology cleanup should pause after this repair; the next
  physical forensics target is a coherent family under `scripts/`.

## Phase 10 status — first scripts research extraction

- The user-performed move placed three allocator-comparison research programs
  under `research/combined_signals/`.
- Their repository-root execution behavior and output paths are preserved.
- `scripts/` remains the home for stable commands and pipeline entry points;
  further combined-signal research moves require their own path/subprocess
  review.

## Phase 11 status — combined-signal research expansion

- Four additional allocator/signal research programs now live under
  `research/combined_signals/`: the two allocator-signal builders and the two
  Monte Carlo analyses.
- Their repository-root discovery, CLI defaults, seeds, iteration defaults,
  and output paths are preserved.
- The v1/v2 builder authority boundary remains unresolved; both are retained.
- `simulate_intelligence_equity_curves.py` remains in `scripts/` because a
  historical stress runner invokes its exact module path.

## Phase 12 status — event-learning evaluation research

- Four event-learning audit/benchmark programs now live under
  `research/event_learning/evaluation/`.
- Dataset audits remain artifact-consuming research commands, not tests; LLM
  benchmark sampling and run comparison retain deterministic selection, join,
  and output behavior.
- `scripts/inspect_evidence_graph.py` remains an operational/heuristic
  evidence-graph diagnostic and was intentionally not moved.
- The four programs continue writing their existing `outputs/intelligence/`
  artifacts; only source ownership changed.

## Preservation blockers

## Phase 16 status — correlation/deformation research topology

- Seven deformation evaluation and correlation-diagnostic programs now live
  under `research/correlation/`.
- Reusable correlation implementation and stable pipeline commands remain in
  their existing locations.
- Deformation metrics, horizons, periods, order comparisons, schemas, and
  output paths were not changed; H20/H100 authority remains unresolved.

## Phase 17 status — threshold-rebalance research topology

- Three comparison/Monte Carlo programs now live under
  `research/threshold_rebalance/`.
- Their repository-root-relative inputs, output paths, schemas, seeds, and
  research calculations were not changed.
- Fast V2, feature-matrix, Fast V3, and matrix-engine strategy commands remain
  under `scripts/`; V2/V3 authority is unresolved and Fast V3 remains
  protected.

## Phase 20 status — peer/spread contract tests

- Added deterministic tests for the existing staged cached, one-pass cached,
  and downstream mean-reversion peer/spread contracts.
- Preserved the staged historical names `ticker_return` and `avg_peer_corr`;
  the canonical one-pass names remain `stock_return` and `top_k_avg_corr`.
- No production peer-search, spread, matrix, signal, or output behavior was
  changed. These tests prepare a future extraction of cached peer search.

## Phase 21 status — staged peer/spread implementation extraction

- Staged cached-matrix peer-search implementation now lives in
  `src/backtester/correlation/peer_search.py`; the historical command remains
  `scripts/large_universe_peer_search.py`.
- Staged cached-matrix peer-basket spread implementation now lives in
  `src/backtester/correlation/peer_spreads.py`; the historical command remains
  `scripts/generate_peer_basket_spreads.py`.
- Phase 20 golden assertions now exercise package ownership and verify that the
  script-visible helpers are the same function objects.
- Package/tabular, staged cached-matrix, and one-pass cached-matrix behavior
  remain separate. The one-pass extraction is deferred.
- No quantitative behavior or schema change was intended. In particular,
  staged `ticker_return` and `avg_peer_corr` remain protected.

## Phase 22 status — documentation authority consolidation

- Established `docs/architecture.md` as the stable current architecture and
  reduced root/project READMEs to navigation and validation entry points.
- Added current large-universe and research-workflow guides and consolidated
  generated-output guidance in `docs/output_policy.md`.
- Grouped 77 versioned and dated intelligence records under
  `docs/history/intelligence/`; current event-learning, operational fallback,
  and historical ML-policy authority remain explicitly distinct.
- Preserved phase records in place behind a historical reorganization index.
  No quantitative implementation, generated output, overlay, worker, or data
  content changed.

## Phase 23 status — MarketState implementation extraction

- Added deterministic contracts for MarketState composition, feature rows,
  rebalance calendars, momentum, capped portfolio weights, lagged returns,
  summaries, schemas, ordering, and script helper compatibility.
- Fast-volatility feature-matrix mechanics now live in
  `src/backtester/decision/market_state_features.py`; the command remains
  `scripts/build_market_state_feature_matrix.py`.
- Historical GARCH portfolio mechanics now live in
  `src/backtester/backtests/market_state_portfolio.py`; the command and its
  `run_backtest` compatibility path remain in
  `scripts/backtest_market_state_portfolio.py`.
- Fast-volatility, GARCH, scan/paper-trade, and threshold-rebalance paths remain
  distinct research generations. No allocator authority or quantitative
  methodology was changed.

## Phase 24 status — final implementation cleanup

- Daily overlapping-position mean-reversion portfolio mechanics now live in
  `src/backtester/backtests/mean_reversion_daily_portfolio.py`; the historical
  command remains `scripts/backtest_mean_reversion_daily_portfolio.py`.
- Deterministic contracts protect signal filtering/ranking, trading-day entry
  and exit alignment, duplicates, exposure sizing, fees, schemas, summaries,
  missing marks, repeatability, and script-helper compatibility.
- `scripts/strategy_scorecard.py` remains a cohesive standalone reporting
  command after read-only forensics found no tracked code callers or clean
  low-risk shared authority boundary.
- One-pass peer/spread, threshold generations, MarketState research commands,
  intelligence stress, and Rust/export workflows remain explicit deferrals or
  legitimate high-risk commands. No methodology or authority changed.

## Phase 25 status — root topology and preservation

- Classified every repository-root lane without moving generated outputs or
  preservation-sensitive ignored content.
- Kept all 66 ignored intelligence overlays in place. A live scan found 289
  source/document files: 132 identical to a plausible tracked counterpart, 156
  different, and one with no tracked counterpart. The aggregate source hash and
  decisions are tracked in `PHASE25_OVERLAY_PRESERVATION.md`.
- Explicitly deferred `dividend-capture/` migration until behavioral contracts
  and ignored-output ownership are established; active stock-backtester code
  does not import it.
- Intentionally retained root `worker_ingest/` as an operational compatibility
  interface because tracked parsers consume its exact local path. No SSH,
  remote worker, credential, provider, data, output, or quantitative behavior
  changed.

## Phase 25B status — root physical cleanup

- Commit `9b44094` preserves all 66 former ignored intelligence overlays as 289
  byte-verified payload files under the tracked, human-readable root archive.
  The 66 old source directories are intentionally absent.
- Archive verification is now lifecycle-correct: `verify` checks only the
  archive, while `verify-sources` remains the explicit pre-removal check used by
  `copy`. Removal verifies the archive both before and after deleting only the
  guarded source paths.
- Four deterministic contracts protect the standalone dividend research
  calendar, schemas, shifted regime window, classifications, and strategy
  signals. Forensics confirm research rather than package ownership.
- All 12 tracked dividend research files now live under
  `research/dividend_capture/`; all eight Python programs remain in their four
  distinct families. The root lane retains 60 ignored output files plus empty
  local `data/` and `notes/` placeholders for Phase 26 compatibility. No output
  file was moved or rewritten.

## Phase 26 status — output taxonomy and preservation

- Inventoried all 34 direct `outputs/` families: 1,501,563,492 bytes in 3,405
  files, plus the separate 4,536,281-byte, 60-file historical dividend lane.
- Classified every major family by role, regenerability, path disposition,
  provenance, writers/readers, durability, and preservation decision. No
  top-level family remains unknown.
- Preserved literal pipeline contracts across signals, correlation/context,
  matrices/cache, Rust, intelligence, MarketState, and worker-derived tables;
  no schema or methodology changed and no H20/H100 or threshold authority was
  chosen.
- Retained all physical artifacts. No candidate met the complete deletion or
  safe-move standard, and moving dividend history would conflict with a
  documented path and a separate `outputs/dividend/` lineage.
- Updated current policy with a minimal manifest standard, shallow placement
  convention, and retention rules for new significant runs. Output organization
  is explicitly classified and sufficient for Reorg V1 freeze.

## Phase 27 status — Reorg V1 freeze

- Re-ran the root and project ten-minute re-entry test from current navigation
  without relying on phase history; all requested authority, pipeline,
  research, validation, tool, output, worker, archive, and compatibility
  surfaces are reachable in at most two documentation hops.
- Verified the physical ownership rules, four intelligence lineages/statuses,
  three peer/spread regimes, MarketState generations, dividend research/output
  split, worker interface, 34-family output inventory, registered paths,
  package initializer exports, generated Git hygiene, and archive integrity.
- Repaired four small current-document inconsistencies: post-removal archive
  verification, moved maintenance-tool ownership, historical overlay-count
  tense, and the operational intelligence-engine output-contract reference.
- Consolidated acceptable post-freeze debt, safe extension rules, the re-entry
  scorecard, and validation evidence in `REORG_V1_FREEZE.md`.
- Decision: `READY_TO_FREEZE`. Reorg V1 physical reorganization is complete;
  dependency-complete user validation remains the acceptance gate before the
  freeze record is committed.

## Phase 15 status — mean-reversion research topology

- Six evaluation, robustness, inspection, and same-universe control programs
  now live under `research/mean_reversion/`.
- Packaged signal construction remains under `src/backtester/signals/`; stable
  pipeline commands remain under `scripts/`.
- Generated outputs, horizons, seeds, Monte Carlo methods, and benchmark
  assumptions were not changed. H20/H100 authority remains unresolved.

## Phase 13 status — training orchestration extraction

- Shared manifest writing, child-step launching, filename-safe float formatting,
  shell quoting, and input-path checks now live in
  `src/backtester/intelligence/training_orchestration.py`.
- The batch, pool, and long-run training command paths remain unchanged; their
  research policy, defaults, child command paths, and output directories remain
  in the wrappers.
- Monitoring remains script-owned because its dataframe/report presentation is
  not yet a shared orchestration contract.
- No training, pool launch, network access, or output generation was performed.

- Historical overlay payloads are recoverable from the tracked archive; the old
  ignored delivery directories are intentionally absent.
- The v2.6.2 overlay documentation has no canonical destination.
- Existing output trees contain both regenerable intermediates and research evidence; official baselines are not yet identified.
- The operational heuristic intelligence path and event-learning research path coexist.

## Explicitly untouched

No production algorithms, strategy behavior, signal formulas, allocators, intelligence behavior, workers, Rust behavior, output schemas, data files, overlays, historical backtests, or generated output trees were moved, deleted, or rewritten. Import changes are limited to the behavior-preserving package topology repairs recorded for the completed phases.

## Future sequence

1. Phase 0: authority, preservation, and contracts — completed.
2. Phase 1A: shared table-I/O extraction — completed by this slice.
3. Phase 1B: artifact/storage behavior normalization; no deletion until manifests and baselines exist.
4. Phase 2: additional shared infrastructure extraction behind compatibility interfaces.
5. Phase 3: gradual command/pipeline/experiment separation.
6. Phase 4: historical and overlay archival after preservation verification.
7. Phase 5: repository topology/navigation — documentation completed; physical
   test move remains blocked by workspace permissions.
8. Phase 6: domain-oriented package restructuring.
9. Phase 7: compatibility, reproducibility, and deprecation validation.

## Candidate cheap wins

- Add a current-workflow index and owner/status fields to the manifests.
- Add offline contract tests for sacred commands and Rust matrix schemas.
- Define official compact baseline manifests before touching large outputs.
- Reconcile dependency specifications in a separate, explicitly approved task.
- Require new research experiments to document ownership, purpose, inputs, outputs, parameters, command/runner, and test or baseline evidence before registry integration.

## User decisions required

- Promote or retain the current feature branch as the reorganization baseline.
- Decide whether heuristic intelligence remains operational.
- Select official durable research baselines.
- Decide which manifested future runs merit durable-baseline promotion; Phase 26
  retained existing output generations without inventing that authority.
