# Next Steps

This is the active roadmap after the market graph fabric session.

## First priority next session

Do not start by adding random new engines.

Start with cleanup and output optimization.

Immediate focus:

    outputs/monte_carlo
    outputs/threshold_rebalance
    outputs/rust_stress

Reason:

The project is now powerful, but output generation is too heavy. Disk cleanliness matters for organization, speed, and laptop longevity.

## Priority 1: Output cleanup

1. Audit outputs/monte_carlo.
2. Keep only final summaries and important benchmark results.
3. Delete or archive curve-heavy duplicate runs.
4. Audit outputs/threshold_rebalance.
5. Remove or compress paired curve folders after preserving summaries.
6. Audit outputs/rust_stress.
7. Keep final stress summaries and delete smoke/sanity runs.
8. Create a signal manifest before pruning outputs/signals.

## Priority 2: Compact-output changes

Patch scripts so large outputs are opt-in.

Add flags:

    --compact
    --save-curves
    --save-plots
    --save-trials
    --save-debug

Default behavior:

    save summary only
    do not save curves
    do not save plots
    do not save trials
    do not create many subfolders

Scripts likely needing this:

    research/threshold_rebalance/monte_carlo_from_feature_matrix.py
    scripts/monte_carlo_market_state.py
    research/threshold_rebalance/compare_threshold_portfolios.py
    scripts/threshold_rebalance_fast_v2.py
    scripts/threshold_rebalance_fast_v3.py
    scripts/threshold_rebalance_matrix_engine.py
    research/mean_reversion/stress_mean_reversion_monte_carlo.py

## Priority 3: Market graph fabric next steps

1. Add visuals/summarize_market_fabric_clusters.py.
2. Read cluster_summary.csv.
3. Output cluster_identity_summary.csv.
4. Include:
       cluster_id
       recurring top stress tickers
       recurring long candidates
       recurring short candidates
       average stress
       average entropy
       average realized volatility
       suggested label
5. Patch visualizer so cluster labels can show names.
6. Add optional cluster identity file argument:
       --cluster-names path/to/cluster_identity_summary.csv

## Priority 4: Stress metric split

Current stress includes forward return, so it is partly realized.

Split into:

    stress_ex_ante
    stress_realized

stress_ex_ante should use only data known at signal date.

Possible stress_ex_ante components:

    realized_vol_z
    corr_degree_z
    entropy_z
    correlation_delta_z
    market regime stress

stress_realized may include:

    abs_forward_return_z
    realized future drawdown
    future volatility expansion

Use stress_ex_ante for research/trading logic.
Use stress_realized for visual diagnosis.

## Priority 5: Sector metadata

Add sector/industry metadata.

Goals:

    compare KMeans clusters against real sectors
    label clusters more intelligently
    detect mixed clusters
    separate true sector continents from high-volatility microcap clusters

Possible outputs:

    cluster_sector_summary.csv
    cluster_identity_summary.csv

## Priority 6: Visual Monte Carlo

Build visual comparison tools:

    actual signals
    same-date random tickers
    random-date random tickers
    long-only
    short-only
    long/short combined
    winner-exclusion
    sector-exclusion

Goal:

Visually inspect whether the strategy is finding real structural distortions or just lucky noisy clusters.

## Priority 7: MP4 and recording polish

Current visualizer can record frames, but export workflow should be cleaner.

Add:

    --record-mp4
    --record-output
    --record-max-frames
    --camera-path
    --bitrate
    --fps

## Priority 8: Backend scaling

Python should not own repeated heavy simulation loops forever.

Long-term architecture:

    Python = orchestration, reporting, visualization launch
    Rust = repeated simulations, sweeps, stress tests, exclusion tests
    CUDA/CuPy = dense matrix-heavy operations
    VisPy = interactive playback

## Current best visual workflow

Combine signals:

    python visuals/combine_long_short_signals.py \
      --long-signals outputs/signals/large_universe_peer_spread_long_top5_v1.parquet \
      --short-signals outputs/signals/large_universe_peer_spread_short_top5_v1.parquet \
      --out outputs/signals/large_universe_peer_spread_long_short_top5_v1.parquet \
      --dedupe

Build final fabric:

    time python visuals/build_market_graph_frames.py \
      --returns-meta /tmp/quant_returns/h100_market_common_stock_only_v3_clipped/returns_meta.json \
      --signals outputs/signals/large_universe_peer_spread_long_short_top5_v1.parquet \
      --context outputs/context/market_context.parquet \
      --out-dir outputs/reports/plots/market_graph_fabric_2020_long_short_cluster_ring_full_kmeans \
      --start-date 2020-02-01 \
      --end-date 2020-06-30 \
      --frame-step-days 5 \
      --lookback 126 \
      --forward-days 60 \
      --max-nodes 2739 \
      --top-k-edges 5 \
      --min-edge-corr 0.42 \
      --z-mode stress \
      --color-mode entropy_z \
      --layout-engine cluster-ring \
      --cluster-count 12 \
      --cluster-anchor-strength 0.70 \
      --force-rebuild

Visualize:

    python visuals/visualize_market_graph_fabric.py \
      --frames-dir outputs/reports/plots/market_graph_fabric_2020_long_short_cluster_ring_full_kmeans \
      --safe-mode \
      --visual-preset stress-fabric \
      --ticker-labels \
      --max-labels 12 \
      --cluster-labels \
      --fps 3 \
      --speed 1 \
      --node-size-metric realized_vol_z \
      --edge-color-mode hybrid

## Reminder

Before more features, clean and optimize output behavior.

The project should become faster and more compact at the same time.
