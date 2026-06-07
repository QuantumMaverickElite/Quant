# Regime Correlation Deformation Engine

## Purpose

The regime correlation deformation engine measures whether the market's correlation structure is compressed or fragmented.

The goal is to detect when stock relationships are becoming tighter or looser across regimes, then use that information as a context layer for mean-reversion and future allocator decisions.

This is different from only asking whether volatility is high. Volatility measures magnitude. Correlation deformation measures market structure.

## Core Idea

For each rolling window, compute pairwise correlations across the universe.

Then compare current pair correlations against calm and stress baselines.

Main feature:

    market_compression_score = avg_current_pair_corr - avg_calm_baseline_pair_corr

Positive values mean the market is more compressed than normal.

Negative values mean the market is more fragmented than normal.

## Compression States

Current state labels:

    BROAD_COMPRESSION
    MODERATE_COMPRESSION
    STABLE
    MODERATE_FRAGMENTATION
    BROAD_FRAGMENTATION

Interpretation:

    BROAD_COMPRESSION:
        Stocks are moving together more than usual.
        Peer relationships are stronger.
        Mean-reversion signals are more structurally confirmed.

    MODERATE_COMPRESSION:
        Mildly supportive for peer-spread mean reversion.

    STABLE:
        Neutral structural state.

    BROAD_FRAGMENTATION:
        Stocks are moving more independently.
        Peer relationships are weaker.
        Mean-reversion should be treated more cautiously, but not banned.

    MODERATE_FRAGMENTATION:
        Historically weaker/dangerous zone for the current mean-reversion setup.

## Files

Engine:

    src/backtester/correlation/regime.py
    scripts/run_regime_correlation_features.py
    scripts/inspect_regime_correlation_features.py
    scripts/merge_regime_deformation_into_context.py

Validation:

    scripts/evaluate_mean_reversion_by_deformation.py
    scripts/evaluate_mean_reversion_by_deformation_subperiods.py
    scripts/evaluate_mean_reversion_by_deformation_yearly.py
    scripts/evaluate_mean_reversion_by_compression_bucket.py
    scripts/plot_regime_deformation_diagnostics.py
    scripts/apply_deformation_weights_to_mean_reversion_signals.py
    scripts/compare_actual_closed_trades.py

Main outputs:

    outputs/correlation/regime_pair_correlations.parquet
    outputs/correlation/regime_correlation_summary.csv
    outputs/correlation/regime_ticker_stress_sensitivity.csv
    outputs/correlation/regime_market_deformation.csv
    outputs/context/market_context_with_regime_deformation.parquet

Best tested deformation-weighted signal:

    outputs/signals/mean_reversion_signals_deformation_weighted_bf085.parquet

Best tested Rust run:

    outputs/rust_stress/h100_deformation_weighted_bf085_100k

## Validation Summary

The first hypothesis was that fragmentation might improve peer-spread mean reversion.

Testing showed the opposite.

Across 5d, 10d, and 20d horizons, broad compression was generally better than fragmentation. The effect was strongest at 20d.

20d validation showed:

    BROAD_COMPRESSION:
        strongest average returns
        strongest win rates
        best long-horizon confirmation

    BROAD_FRAGMENTATION:
        weak or flat on average

    MODERATE_FRAGMENTATION:
        often poor

Subperiod tests showed that broad compression remained useful even outside the 2020-2021 period.

## Weight Experiment

The best simple tested weighting so far is bf085:

    BROAD_COMPRESSION:       1.15
    MODERATE_COMPRESSION:    1.05
    STABLE:                  1.00
    BROAD_FRAGMENTATION:     0.85
    MODERATE_FRAGMENTATION:  0.75

This is intentionally mild.

It is not a hard filter.

## 100k Rust Stress Result

Baseline:

    Final equity: $31,705.30
    Return: 2.17x
    Max drawdown: -32.93%
    Win rate: 48.77%
    Sharpe-like: 0.7476
    Random-date percentile: 48.93%
    Same-date percentile: 83.79%

bf085 deformation-weighted:

    Final equity: $32,261.47
    Return: 2.23x
    Max drawdown: -33.07%
    Win rate: 49.34%
    Sharpe-like: 0.7544
    Random-date percentile: 52.75%
    Same-date percentile: 83.04%

Interpretation:

    bf085 improved final equity, win rate, Sharpe-like score, and random-date percentile.
    It slightly worsened drawdown and same-date percentile.

Conclusion:

    bf085 is promising but should remain experimental.
    It is a subtle ranking adjustment, not a final allocator rule.

## Closed-Trade Attribution

Actual closed-trade comparison showed:

    Added by weighting:
        37 trades
        avg trade return: 9.22%
        win rate: 70.27%
        total PnL: +2924.88

    Removed by weighting:
        36 trades
        avg trade return: 6.22%
        win rate: 55.56%
        total PnL: +1812.69

This means the deformation layer improved trade selection on average.

However, some removed trades were large winners. Therefore the layer should not become a hard filter.

## Current Interpretation

The best interpretation is:

    Compression is a confirmation regime.
    Fragmentation is not a ban.
    Fragmentation should receive a penalty so only stronger signals survive.
    Moderate fragmentation is the clearest danger zone.

## Market Fabric Integration

The market fabric should use deformation as a structural field:

    market_compression_score
    compression_state
    compression_percentile
    fragmentation_percentile

Possible visual uses:

    Node/edge intensity increases during compression.
    Graph loosens during fragmentation.
    Cluster merge score rises when correlations compress.
    Cluster instability rises when fragmentation dominates.

The deformation engine should eventually support:

    normal market graph
    stress/compression graph
    fragmentation graph
    difference graph

## Pseudo-Allocator Integration

The pseudo-allocator should treat deformation as a confidence modifier.

Initial experimental rule:

    deformation_weight =
        1.15 if BROAD_COMPRESSION
        1.05 if MODERATE_COMPRESSION
        1.00 if STABLE
        0.85 if BROAD_FRAGMENTATION
        0.75 if MODERATE_FRAGMENTATION

Then:

    deformation_adjusted_confidence =
        context_adjusted_confidence * deformation_weight

This should remain behind an explicit experiment flag until tested across more universes, horizons, and selection rules.

## Suggested Architecture

Market context:

    volatility_state
    entropy_state
    context_weight

Regime deformation:

    market_compression_score
    compression_state
    compression_percentile
    fragmentation_percentile

Mean-reversion signal:

    confidence
    adjusted_confidence

Pseudo-allocator:

    context_weight
    deformation_weight
    final_signal_score

Pseudo-allocator formula:

    final_signal_score =
        raw_signal_confidence
        * context_weight
        * deformation_weight
        * optional_portfolio_weight

For now, do not bury this inside the main allocator. Keep it as an experimental layer:

    scripts/apply_deformation_weights_to_mean_reversion_signals.py

## Next Tests

Before making this default:

    1. Test on larger/broader universes.
    2. Test different hold periods.
    3. Test top-n sensitivity.
    4. Test threshold sensitivity.
    5. Test long/short combined signals.
    6. Add deformation features to market fabric visuals.
    7. Add pseudo-allocator scorecard comparison.
    8. Build allocator feature table.

## Proposed Allocator Feature Table

Next concrete build step:

    scripts/build_pseudo_allocator_feature_table.py

This should merge:

    outputs/signals/mean_reversion_signals_context_adjusted.parquet
    outputs/context/market_context_with_regime_deformation.parquet
    outputs/correlation/regime_ticker_stress_sensitivity.csv

Output:

    outputs/allocator/pseudo_allocator_feature_table.parquet

Suggested columns:

    date
    ticker
    direction
    confidence
    context_weight
    adjusted_confidence
    market_compression_score
    compression_state
    compression_percentile
    fragmentation_percentile
    deformation_weight
    deformation_adjusted_confidence
    ticker_stress_sensitivity
    final_signal_score

This table becomes the bridge between regime deformation, market fabric, and the pseudo-allocator.

## Allocator-Aware Market Fabric Visual

The allocator-aware market fabric connects:

    mean-reversion signals
    context/regime deformation
    pseudo-allocator feature table
    allocator visual overlay
    market graph fabric

Main generated files:

    outputs/allocator/pseudo_allocator_feature_table.parquet
    outputs/market_fabric/allocator_overlay.parquet
    outputs/market_fabric/allocator_visual_overlay.parquet

The clean visual overlay has one row per date/ticker and contains:

    final_signal_score
    allocator_rank
    compression_state
    fabric_regime_group
    fabric_edge_mode
    fabric_node_role
    node_size_score
    node_alpha_score
    is_top_1_allocator_pick
    is_top_3_allocator_pick
    is_top_5_allocator_pick

The market graph frame builder itself is not allocator-aware yet. Instead, we use a post-processing step:

    scripts/augment_market_graph_frames_with_allocator_overlay.py

This injects allocator arrays into cached frame `.npz` files.

The visualizer then uses:

    --use-allocator-overlay
    --allocator-highlight-top
    --allocator-size-boost

Current preferred visual settings:

    --visual-preset clean-points
    --node-size 2.8
    --node-size-metric none
    --edge-cyan
    --edge-alpha 0.14
    --edge-width 0.08
    --allocator-size-boost 5.0

Helper command:

    ./scripts/run_allocator_market_fabric_latest.sh 2026-05-27

Interpretation:

    The full market is shown as the background correlation fabric.
    Allocator candidates are enlarged and highlighted inside the full market.
    Compression/fragmentation fields come from the regime deformation engine.
    In broad fragmentation, the graph should visually loosen while only high-score candidates remain highlighted.

Current latest allocator candidates on 2026-05-27:

    NVDA
    WMT
    WFC
    BAC
    COST
    GOOGL

Important note:

    A low allocator overlay match rate is normal in whole-market mode.
    The market fabric may contain 1000+ stocks, while the allocator overlay only highlights active signal candidates for that date.
