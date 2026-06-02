# Market Graph Fabric Visualizer

The Market Graph Fabric visualizer is an interactive market-structure visualization system.

Core idea:

    stocks = nodes
    correlations = stitching / edges
    clusters = market continents
    Z height = stress
    node color = entropy
    node size = realized volatility
    edge color = correlation strength plus tightening or loosening
    cyan labels = long candidates
    magenta labels = short candidates

This tool is meant to show how the market correlation fabric changes over time.

## Main files

    visuals/build_market_graph_frames.py

Builds cached graph fabric frames from returns, signals, and market context.

    visuals/visualize_market_graph_fabric.py

Plays cached graph fabric frames interactively using VisPy.

    visuals/combine_long_short_signals.py

Combines separate long and short peer-spread signal parquet files into one long/short signal file.

## Dependencies

The cluster-ring layout uses scikit-learn for KMeans clustering.

Required dependency:

    scikit-learn>=1.8.0

If scikit-learn is missing, the builder falls back to weaker angle-based clustering.

CUDA/CuPy is optional. CUDA works in the current environment, but CPU has been faster for smaller runs because GPU transfer overhead can dominate.

## Recommended default visual configuration

    layout-engine = cluster-ring
    edge-color-mode = hybrid
    z-mode = stress
    color-mode = entropy_z
    node-size-metric = realized_vol_z
    cluster labels = on
    ticker labels = on
    long labels = cyan
    short labels = magenta

## Combine long and short signals

    python visuals/combine_long_short_signals.py \
      --long-signals outputs/signals/large_universe_peer_spread_long_top5_v1.parquet \
      --short-signals outputs/signals/large_universe_peer_spread_short_top5_v1.parquet \
      --out outputs/signals/large_universe_peer_spread_long_short_top5_v1.parquet \
      --dedupe

This creates:

    outputs/signals/large_universe_peer_spread_long_short_top5_v1.parquet

The combined file should contain:

    direction = long
    direction = short

## Build full-market 2020 long/short fabric

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

This writes:

    manifest.json
    frame_summary.csv
    cluster_summary.csv
    frames/

## Visualize the fabric

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

## Controls

    Space = pause/play
    + / - = speed up / slow down
    E = toggle edges
    H = toggle HUD
    T = toggle axes
    C = toggle cluster labels
    1 = default camera
    2 = top camera
    3 = side camera
    V = record frames
    Q = quit

## Layout engines

    corr-pca-fast

Fast scalable correlation geometry. Good for large and long runs.

    cluster-ring

Cluster-aware KMeans layout. Produces market continents. This is the best current visual mode.

    mds

Older classical MDS layout. More expensive and less scalable.

## Edge color modes

    corr

Shows correlation strength.

    delta

Shows correlation tightening or loosening compared with the previous frame.

    hybrid

Shows both correlation strength and tightening/loosening. This is the preferred default.

## Stress metric

Current stress is a blended diagnostic market-pressure score:

    stress =
      0.40 * realized_vol_z
    + 0.25 * corr_degree_z
    + 0.25 * entropy_z
    + 0.10 * abs_forward_return_z

Interpretation:

    realized_vol_z = volatility heat / kinetic energy
    corr_degree_z = correlation crowding / market stitching
    entropy_z = disorder or diffuse peer relationships
    abs_forward_return_z = large realized forward movement

Important: current stress includes forward return. That means it is partly diagnostic/post-analysis.

Future split:

    stress_ex_ante = only information known at the signal date
    stress_realized = includes forward movement for visual diagnosis

## Output summaries

frame_summary.csv has one row per frame.

Useful columns:

    date
    nodes
    edges
    avg_edge_corr
    avg_edge_corr_delta
    avg_abs_edge_corr_delta
    stress_mean
    stress_p95
    entropy_z_mean
    realized_vol_z_mean

cluster_summary.csv has one row per cluster per frame.

Useful columns:

    cluster_id
    node_count
    long_count
    short_count
    top_tickers_by_stress
    top_longs
    top_shorts
    stress_mean
    stress_p95
    entropy_z_mean
    realized_vol_z_mean
    forward_return_mean

## CUDA notes

CUDA/CuPy works, but CPU is currently better for smaller builds.

Default:

    cluster-ring + CPU

Use CUDA only for heavier experiments:

    --use-cupy

CUDA is most likely to help when:

    node count is very high
    frame count is very high
    correlation workloads become very dense
    visual Monte Carlo experiments are added

## Current status

Working:

    graph-based stock-node fabric
    cluster-ring layout
    KMeans clustering through scikit-learn
    long/short combined signals
    balanced long/short labels
    cluster labels
    frame_summary.csv
    cluster_summary.csv
    CUDA smoke test

Best known visual command:

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

## Future plans

Near term:

    1. Add cluster identity summary script.
    2. Add human-readable cluster names.
    3. Let the visualizer show cluster names instead of only C0, C1, etc.
    4. Split stress into stress_ex_ante and stress_realized.
    5. Add better legends/colorbars.
    6. Improve MP4 recording/export.

Medium term:

    1. Add sector and industry metadata.
    2. Compare KMeans clusters against real sectors.
    3. Add visual Monte Carlo runs.
    4. Add cluster-level performance summaries.
    5. Add long/short candidate path tracing.

Long term:

    1. Move heavy rolling correlation/top-k graph building into Rust.
    2. Use Python mainly for orchestration, reports, and visualization.
    3. Use CUDA/CuPy for dense matrix-heavy workloads.
    4. Build market-scale daily animations over many years.
    5. Build a visual research dashboard for the allocator and strategy engines.
