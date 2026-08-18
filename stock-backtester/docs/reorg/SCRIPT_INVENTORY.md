zsh:1: command not found: scripts.csv
<string>:1: SyntaxWarning: "\|" is an invalid escape sequence. Such sequences will not work in the future. Did you mean "\\|"? A raw string is also an option.
# Script Inventory

Machine-readable source: [scripts.csv](scripts.csv).

Classification is evidence-assisted static analysis of imports, references, documentation, path contracts, and directory role. UNCERTAIN means the repository did not provide enough evidence for a safe semantic decision.

Phase 1/2/6 migration note: the four ML-policy scripts remain compatibility wrappers around `src/backtester/intelligence/ml_policy/`; their policy calculations, CLI contracts, and output schemas were not changed. See [ML_POLICY_SCRIPT_FAMILY.md](ML_POLICY_SCRIPT_FAMILY.md).

Phase 3 note: the registry pilot describes those four commands and a small number of mean-reversion/large-universe workflows without reclassifying the remaining 186-script inventory. Event-learning audit and benchmark programs now live under `research/event_learning/evaluation/`; they are research utilities, not tests.

| path | classification | subsystem | status | sacred | migration_risk | confidence | likely_destination |
|---|---|---|---|---|---|---|---|
| scripts/__init__.py | UNCERTAIN | general | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/apply_calibrated_intelligence.py | TRAINING | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/apply_context_to_mean_reversion_signals.py | DATA TRANSFORMATION | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/apply_deformation_weights_to_mean_reversion_signals.py | DATA TRANSFORMATION | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/apply_intelligence_to_signals.py | DATA TRANSFORMATION | intelligence | ACTIVE RESEARCH | no | HIGH | MEDIUM | src/quant_research or research/experiments |
| scripts/apply_ml_policy_strength.py | DATA TRANSFORMATION | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/apply_survivable_volatility.py | DATA TRANSFORMATION | market_state | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/archive/visual_experiments/build_market_fabric_frames.py | ARCHIVED / HISTORICAL | market_fabric | HISTORICAL | no | MEDIUM | HIGH | research/history or archive manifest |
| scripts/archive/visual_experiments/filter_peer_spread_signals_with_cooldown.py | ARCHIVED / HISTORICAL | market_fabric | HISTORICAL | no | MEDIUM | HIGH | research/history or archive manifest |
| scripts/archive/visual_experiments/plot_market_manifold.py | ARCHIVED / HISTORICAL | market_fabric | HISTORICAL | no | MEDIUM | HIGH | research/history or archive manifest |
| scripts/archive/visual_experiments/plot_rust_spaghetti.py | ARCHIVED / HISTORICAL | market_fabric | HISTORICAL | no | MEDIUM | HIGH | research/history or archive manifest |
| scripts/archive/visual_experiments/render_market_fabric.py | ARCHIVED / HISTORICAL | market_fabric | HISTORICAL | no | MEDIUM | HIGH | research/history or archive manifest |
| scripts/archive/visual_experiments/visualize_market_fabric_vispy.py | ARCHIVED / HISTORICAL | market_fabric | HISTORICAL | no | MEDIUM | HIGH | research/history or archive manifest |
| scripts/archive_compact_artifact_to_git.py | MAINTENANCE TOOL | general | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| research/event_learning/evaluation/audit_event_day_impact_dataset.py | AUDIT COMMAND | event_learning_evaluation | ACTIVE RESEARCH | no | MEDIUM | HIGH | research/event_learning/evaluation |
| research/event_learning/evaluation/audit_event_impact_dataset.py | AUDIT COMMAND | event_learning_evaluation | ACTIVE RESEARCH | no | MEDIUM | HIGH | research/event_learning/evaluation |
| scripts/audit_historical_source_mix.py | MAINTENANCE TOOL | general | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/audit_quant_outputs.py | MAINTENANCE TOOL | general | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/augment_market_graph_frames_with_allocator_overlay.py | UNCERTAIN | market_fabric | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/augment_market_graph_frames_with_trade_overlay.py | UNCERTAIN | market_fabric | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/backtest_market_state_portfolio.py | COMMAND / ENTRY POINT | market_state | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/backtest_mean_reversion_daily_portfolio.py | PIPELINE ORCHESTRATOR | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| research/mean_reversion/backtest_mean_reversion_monte_carlo.py | EVALUATION / BENCHMARK | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/mean_reversion |
| scripts/backtest_options_overlay.py | COMMAND / ENTRY POINT | options_volatility | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/benchmark_array_backend.py | EVALUATION / BENCHMARK | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/benchmark_matrix_batch_ops.py | EVALUATION / BENCHMARK | allocator_matrix | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| research/mean_reversion/benchmark_same_universe_buy_hold.py | VALIDATION / DIAGNOSTIC | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/mean_reversion |
| research/combined_signals/build_allocator_intelligence_signals.py | DATA TRANSFORMATION | combined_signals | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/combined_signals |
| research/combined_signals/build_allocator_intelligence_signals_v2.py | DATA TRANSFORMATION | combined_signals | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/combined_signals |
| scripts/build_combined_market_signal_state.py | DATA TRANSFORMATION | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_contextual_event_features.py | DATA TRANSFORMATION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_entity_master.py | DATA TRANSFORMATION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_event_day_impact_dataset.py | DATA TRANSFORMATION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_event_fact_table.py | DATA TRANSFORMATION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_event_impact_dataset.py | DATA TRANSFORMATION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_historical_intelligence_panel_seed.py | DATA TRANSFORMATION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_historical_news_features.py | DATA TRANSFORMATION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_historical_sec_features.py | DATA TRANSFORMATION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_intelligence_calibration_dataset.py | TRAINING | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_intelligence_price_features.py | DATA TRANSFORMATION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| research/event_learning/evaluation/build_llm_benchmark_sample.py | BENCHMARK / RESEARCH EXPERIMENT | event_learning_evaluation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/event_learning/evaluation |
| scripts/build_market_cap_cache.py | DATA TRANSFORMATION | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_market_fabric_allocator_overlay.py | VISUALIZATION | market_fabric | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_market_fabric_trade_overlay.py | VISUALIZATION | market_fabric | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_market_fabric_visual_overlay.py | VISUALIZATION | market_fabric | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_market_fabric_visual_overlay_from_combined_state.py | VISUALIZATION | market_fabric | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_market_state_feature_matrix.py | DATA TRANSFORMATION | allocator_matrix | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_outcome_labels.py | DATA TRANSFORMATION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_pseudo_allocator_feature_table.py | DATA TRANSFORMATION | allocator_matrix | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_survivable_vol_price_features.py | DATA TRANSFORMATION | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_ticker_universe_sec.py | DATA TRANSFORMATION | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/build_universe.py | DATA TRANSFORMATION | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/calibrate_intelligence_weights.py | TRAINING | intelligence | ACTIVE RESEARCH | no | HIGH | MEDIUM | src/quant_research or research/experiments |
| scripts/check_intelligence_nlp.py | UNCERTAIN | intelligence | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/classify_event_facts_llm.py | TRAINING | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/compact_intelligence_run.py | MAINTENANCE TOOL | intelligence | ACTIVE RESEARCH | no | HIGH | HIGH | src/quant_research or research/experiments |
| scripts/compare_actual_closed_trades.py | EVALUATION / BENCHMARK | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| research/combined_signals/compare_allocator_intelligence.py | EVALUATION / BENCHMARK | combined_signals | ACTIVE RESEARCH | no | HIGH | MEDIUM | research/combined_signals |
| research/combined_signals/compare_allocator_rankings.py | EVALUATION / BENCHMARK | combined_signals | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/combined_signals |
| research/correlation/compare_deformation_weight_changed_orders.py | EVALUATION / BENCHMARK | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/correlation |
| scripts/compare_equity_layers.py | EVALUATION / BENCHMARK | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/compare_fast_v2_drift_thresholds.py | EVALUATION / BENCHMARK | allocator_matrix | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| research/event_learning/evaluation/compare_llm_classification_runs.py | BENCHMARK / RESEARCH EXPERIMENT | event_learning_evaluation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/event_learning/evaluation |
| scripts/compare_rebalance_frequencies.py | EVALUATION / BENCHMARK | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/compare_regime_by_year.py | EVALUATION / BENCHMARK | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/compare_regime_runs.py | EVALUATION / BENCHMARK | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/compare_strategy_vs_buy_hold.py | EVALUATION / BENCHMARK | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/compare_threshold_portfolios.py | EVALUATION / BENCHMARK | allocator_matrix | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/create_market_cap_boost_signals.py | DATA TRANSFORMATION | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/create_market_cap_rank_bonus_signals.py | DATA TRANSFORMATION | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/create_market_cap_tiebreaker_signals.py | DATA TRANSFORMATION | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/create_survivable_vol_backtest_signals.py | DATA TRANSFORMATION | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/create_survivable_vol_penalty_only_signals.py | DATA TRANSFORMATION | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| research/combined_signals/diagnose_allocator_intelligence.py | EVALUATION / BENCHMARK | combined_signals | ACTIVE RESEARCH | no | HIGH | MEDIUM | research/combined_signals |
| research/mean_reversion/evaluate_mean_reversion_by_compression_bucket.py | EVALUATION / BENCHMARK | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/mean_reversion |
| research/correlation/evaluate_mean_reversion_by_deformation.py | EVALUATION / BENCHMARK | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/correlation |
| research/correlation/evaluate_mean_reversion_by_deformation_subperiods.py | EVALUATION / BENCHMARK | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/correlation |
| research/correlation/evaluate_mean_reversion_by_deformation_yearly.py | EVALUATION / BENCHMARK | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/correlation |
| research/mean_reversion/evaluate_mean_reversion_signals.py | EVALUATION / BENCHMARK | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/mean_reversion |
| scripts/export_combined_allocator_signals.py | DATA TRANSFORMATION | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/export_orders_from_signals_with_cached_prices.py | DATA TRANSFORMATION | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/export_returns_matrix.py | DATA TRANSFORMATION | allocator_matrix | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/export_rust_matrix_inputs.py | COMMAND / ENTRY POINT | allocator_matrix | ACTIVE RESEARCH | yes | HIGH | HIGH | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/export_rust_portfolio_inputs.py | DATA TRANSFORMATION | rust_stress | ACTIVE RESEARCH | no | HIGH | MEDIUM | src/quant_research or research/experiments |
| scripts/export_rust_stress_inputs.py | DATA TRANSFORMATION | rust_stress | ACTIVE RESEARCH | no | HIGH | MEDIUM | src/quant_research or research/experiments |
| scripts/extract_contextual_events.py | DATA TRANSFORMATION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/fetch_historical_intelligence_sources.py | DATA INGESTION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/fetch_historical_news_sources.py | DATA INGESTION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/fetch_intelligence_sources.py | DATA INGESTION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/fetch_sec_intelligence_sources.py | DATA INGESTION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/filter_cached_price_matrix.py | UNCERTAIN | allocator_matrix | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/generate_peer_basket_spreads.py | UNCERTAIN | correlation_deformation | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| research/correlation/inspect_correlation_features.py | VALIDATION / DIAGNOSTIC | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/correlation |
| scripts/inspect_evidence_graph.py | DEBUG / INSPECTION TOOL | operational_intelligence | OPERATIONAL / FALLBACK | no | MEDIUM | HIGH | scripts/ |
| research/mean_reversion/inspect_mean_reversion_signals.py | VALIDATION / DIAGNOSTIC | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/mean_reversion |
| research/correlation/inspect_regime_correlation_features.py | VALIDATION / DIAGNOSTIC | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/correlation |
| scripts/join_llm_classifications.py | TRAINING | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/label_event_forward_outcomes.py | TRAINING | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/large_universe_peer_search.py | UNCERTAIN | correlation_deformation | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/launch_long_intelligence_training.py | TRAINING | intelligence | ACTIVE RESEARCH | no | HIGH | MEDIUM | src/quant_research or research/experiments |
| scripts/legacy/intelligence_heuristics/score_cbworker_news_relevance.py | ARCHIVED / HISTORICAL | intelligence | HISTORICAL | no | HIGH | HIGH | research/history or archive manifest |
| scripts/legacy/intelligence_heuristics/score_cbworker_news_relevance_market.py | ARCHIVED / HISTORICAL | intelligence | HISTORICAL | no | HIGH | HIGH | research/history or archive manifest |
| scripts/legacy/intelligence_heuristics/score_cbworker_news_signal_quality.py | ARCHIVED / HISTORICAL | intelligence | HISTORICAL | no | HIGH | HIGH | research/history or archive manifest |
| scripts/live_intelligence_cache.py | UNCERTAIN | intelligence | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/live_intraday_intelligence_loop.py | UNCERTAIN | intelligence | UNCERTAIN | no | HIGH | LOW | USER DECISION REQUIRED |
| scripts/merge_historical_sources.py | DATA INGESTION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/merge_regime_deformation_into_context.py | DATA TRANSFORMATION | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/monitor_intelligence_training.py | TRAINING | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/monitor_long_intelligence_training.py | TRAINING | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| research/combined_signals/monte_carlo_allocator_intelligence.py | EVALUATION / BENCHMARK | combined_signals | ACTIVE RESEARCH | no | HIGH | MEDIUM | research/combined_signals |
| scripts/monte_carlo_from_feature_matrix.py | EVALUATION / BENCHMARK | allocator_matrix | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/monte_carlo_market_state.py | EVALUATION / BENCHMARK | market_state | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| research/combined_signals/monte_carlo_strategy_grid.py | EVALUATION / BENCHMARK | combined_signals | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/combined_signals |
| scripts/monte_carlo_walk_forward_predictions.py | TRAINING | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/normalize_worker_sources.py | DATA INGESTION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/parse_cbworker_news_sources.py | DATA INGESTION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/parse_cbworker_yahoo_chart.py | DATA INGESTION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/permutation_test_ml_policy.py | UNCERTAIN | general | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/plot_rebalance_median_curves.py | VISUALIZATION | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| research/correlation/plot_regime_deformation_diagnostics.py | VISUALIZATION | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/correlation |
| scripts/plot_rust_stress_report.py | VISUALIZATION | rust_stress | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/prune_intelligence_training_runs.py | MAINTENANCE TOOL | intelligence | ACTIVE RESEARCH | no | HIGH | HIGH | src/quant_research or research/experiments |
| tools/reorg/reorg_audit.py | MAINTENANCE TOOL | reorganization | ACTIVE RESEARCH | no | MEDIUM | HIGH | tools/reorg |
| tools/reorg/reorg_file_inventory.py | MAINTENANCE TOOL | reorganization | ACTIVE RESEARCH | no | MEDIUM | HIGH | tools/reorg |
| tools/reorg/reorg_import_graph.py | MAINTENANCE TOOL | reorganization | ACTIVE RESEARCH | no | MEDIUM | HIGH | tools/reorg |
| tools/reorg/reorg_overlay_inventory.py | MAINTENANCE TOOL | reorganization | ACTIVE RESEARCH | no | MEDIUM | HIGH | tools/reorg |
| tools/reorg/reorg_sacred_smoke.py | MAINTENANCE TOOL | reorganization | ACTIVE RESEARCH | no | MEDIUM | HIGH | tools/reorg |
| scripts/resolve_entities.py | DATA TRANSFORMATION | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/run_allocator_market_fabric_latest.sh | VISUALIZATION | market_fabric | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/run_combined_allocator_market_fabric.sh | VISUALIZATION | market_fabric | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/run_combined_allocator_market_fabric_latest.sh | VISUALIZATION | market_fabric | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/run_correlation_features.py | PIPELINE ORCHESTRATOR | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/run_historical_intelligence_stress.py | EVALUATION / BENCHMARK | intelligence | ACTIVE RESEARCH | no | HIGH | MEDIUM | src/quant_research or research/experiments |
| scripts/run_intelligence_training_batch.py | TRAINING | intelligence | ACTIVE RESEARCH | no | HIGH | MEDIUM | src/quant_research or research/experiments |
| scripts/run_llm_classification_batch.py | TRAINING | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/run_market_context_features.py | PIPELINE ORCHESTRATOR | market_state | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/run_market_intelligence.py | COMMAND / ENTRY POINT | intelligence | ACTIVE RESEARCH | no | HIGH | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/run_market_intelligence_batch.py | COMMAND / ENTRY POINT | intelligence | ACTIVE RESEARCH | no | HIGH | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/run_market_intelligence_demo.py | COMMAND / ENTRY POINT | intelligence | ACTIVE RESEARCH | no | HIGH | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/run_market_intelligence_live.py | COMMAND / ENTRY POINT | intelligence | ACTIVE RESEARCH | yes | HIGH | HIGH | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/run_mean_reversion_signals.py | COMMAND / ENTRY POINT | mean_reversion | ACTIVE RESEARCH | yes | HIGH | HIGH | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/run_multi_period_intelligence_research.py | COMMAND / ENTRY POINT | intelligence | ACTIVE RESEARCH | no | HIGH | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/run_nlp_event_smoke.py | COMMAND / ENTRY POINT | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/run_peer_spread_features.py | PIPELINE ORCHESTRATOR | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/run_peer_spread_features_from_cached_matrix.py | PIPELINE ORCHESTRATOR | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/run_pool_intelligence_training.py | TRAINING | intelligence | ACTIVE RESEARCH | no | HIGH | MEDIUM | src/quant_research or research/experiments |
| scripts/run_regime_basket.py | COMMAND / ENTRY POINT | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/run_regime_correlation_features.py | PIPELINE ORCHESTRATOR | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/run_worker_sources_to_events.sh | WORKER / REMOTE TOOLING | intelligence | ACTIVE / EXTERNAL CONTRACT | no | MEDIUM | HIGH | pipelines/intelligence or worker tooling |
| scripts/scan_market_state.py | UNCERTAIN | market_state | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/score_event_opportunities.py | EVALUATION / BENCHMARK | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/score_historical_news_sentiment.py | EVALUATION / BENCHMARK | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/score_ml_research_gates.py | EVALUATION / BENCHMARK | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/simulate_intelligence_equity_curves.py | UNCERTAIN | intelligence | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/smoke_correlation_from_prices.py | TEST / SMOKE | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/smoke_correlation_tracker.py | TEST / SMOKE | correlation_deformation | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/strategy_scorecard.py | EVALUATION / BENCHMARK | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| research/mean_reversion/stress_mean_reversion_monte_carlo.py | EVALUATION / BENCHMARK | mean_reversion | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | research/mean_reversion |
| scripts/suggest_market_fabric_cluster_labels.py | VISUALIZATION | market_fabric | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/summarize_intelligence_training_run.py | TRAINING | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/summarize_market_intelligence.py | EVALUATION / BENCHMARK | intelligence | ACTIVE RESEARCH | no | HIGH | MEDIUM | src/quant_research or research/experiments |
| scripts/summarize_regime_basket.py | EVALUATION / BENCHMARK | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/summarize_rust_stress_runs.py | EVALUATION / BENCHMARK | rust_stress | ACTIVE RESEARCH | no | HIGH | MEDIUM | src/quant_research or research/experiments |
| scripts/sweep_ml_policy_strength.py | UNCERTAIN | general | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/test_entropy_engine.py | TEST / SMOKE | market_fabric | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/test_market_state.py | TEST / SMOKE | market_state | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/test_market_state_trades.py | TEST / SMOKE | market_state | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/test_options_overlay.py | TEST / SMOKE | options_volatility | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/test_position_sizing.py | TEST / SMOKE | general | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/test_real_market_state.py | TEST / SMOKE | market_state | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/test_real_volatility_decision.py | TEST / SMOKE | market_state | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/test_regime_router.py | TEST / SMOKE | market_state | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/test_survivable_volatility.py | TEST / SMOKE | market_state | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/test_volatility_decision.py | TEST / SMOKE | market_state | ACTIVE RESEARCH | no | MEDIUM | HIGH | src/quant_research or research/experiments |
| scripts/threshold_rebalance_fast_v2.py | UNCERTAIN | allocator_matrix | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/threshold_rebalance_fast_v3.py | COMMAND / ENTRY POINT | allocator_matrix | ACTIVE RESEARCH | yes | HIGH | HIGH | scripts compatibility wrapper + src/quant_research/pipelines |
| scripts/threshold_rebalance_from_feature_matrix.py | UNCERTAIN | allocator_matrix | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/threshold_rebalance_matrix_engine.py | UNCERTAIN | allocator_matrix | UNCERTAIN | no | MEDIUM | LOW | USER DECISION REQUIRED |
| scripts/train_event_day_baseline.py | TRAINING | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/validate_ml_policy_candidate.py | EVALUATION / BENCHMARK | general | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/walk_forward_intelligence_calibration.py | TRAINING | intelligence | ACTIVE RESEARCH | no | MEDIUM | MEDIUM | src/quant_research or research/experiments |
| scripts/workers/redact_stream.py | WORKER / REMOTE TOOLING | intelligence | ACTIVE / EXTERNAL CONTRACT | no | HIGH | HIGH | pipelines/intelligence or worker tooling |
| scripts/workers/run_balanced_source_fetch_worker.sh | WORKER / REMOTE TOOLING | intelligence | ACTIVE / EXTERNAL CONTRACT | no | HIGH | HIGH | pipelines/intelligence or worker tooling |
| scripts/workers/run_source_fetch_worker.sh | WORKER / REMOTE TOOLING | intelligence | ACTIVE / EXTERNAL CONTRACT | no | HIGH | HIGH | pipelines/intelligence or worker tooling |
| scripts/workers/send_llm_worker_bundle.sh | WORKER / REMOTE TOOLING | intelligence | ACTIVE / EXTERNAL CONTRACT | no | HIGH | HIGH | pipelines/intelligence or worker tooling |
| scripts/workers/sync_worker_env.sh | WORKER / REMOTE TOOLING | intelligence | ACTIVE / EXTERNAL CONTRACT | no | HIGH | HIGH | pipelines/intelligence or worker tooling |
