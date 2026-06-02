# 2026-06-02 Market Graph Fabric Session

This document summarizes the long build session where the market graph fabric visualizer became a serious research tool.

## What was built

We built a market graph fabric system where:

    stocks = nodes
    correlations = edges / stitching
    clusters = market continents
    Z height = stress
    node color = entropy_z
    node size = realized_vol_z
    cyan labels = long candidates
    magenta labels = short candidates

The final working system uses:

    visuals/build_market_graph_frames.py
    visuals/visualize_market_graph_fabric.py
    visuals/combine_long_short_signals.py

## Major upgrades completed

1. Added a graph-based stock-node fabric visualizer.
2. Added correlation-based layouts.
3. Added corr-pca-fast layout to avoid slow O(n^3)-style scaling from classical MDS.
4. Added cluster-ring layout.
5. Added KMeans cluster-ring support through scikit-learn.
6. Added scikit-learn to requirements.txt.
7. Added long/short combined signal support.
8. Added balanced long/short ticker labels so combined mode shows both sides.
9. Changed short labels to magenta so they stand out against entropy heat.
10. Added cluster labels with C toggle.
11. Added frame_summary.csv.
12. Added cluster_summary.csv.
13. Added duplicate snap-date skipping for long historical runs.
14. Added CUDA/CuPy smoke tests.
15. Confirmed CUDA works, but CPU is faster for small graph builds.
16. Archived older visual experiment scripts.
17. Documented the visual workflow in visuals/README.md.
18. Cleaned duplicate generated visual output folders.

## Final preserved visual run

Current preserved final run:

    outputs/reports/plots/market_graph_fabric_2020_long_short_cluster_ring_full_kmeans

This run contains:

    manifest.json
    frame_summary.csv
    cluster_summary.csv
    frames/

The build used:

    max_nodes = 2739
    frames = 31
    top_k_edges = 5
    z-mode = stress
    color-mode = entropy_z
    layout-engine = cluster-ring
    cluster-count = 12
    cluster-anchor-strength = 0.70
    long candidates per frame = 5
    short candidates per frame = 5

## Main commands

Combine long and short signals:

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

Visualize final fabric:

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

    Space = play / pause
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

## What stress currently means

Current stress is a diagnostic blended metric:

    stress =
      0.40 * realized_vol_z
    + 0.25 * corr_degree_z
    + 0.25 * entropy_z
    + 0.10 * abs_forward_return_z

Interpretation:

    realized_vol_z = volatility heat
    corr_degree_z = correlation crowding
    entropy_z = relationship disorder / diffuse peer structure
    abs_forward_return_z = large realized future movement

Important limitation:

Current stress includes forward return, so it is partly realized/post-analysis.

Future split:

    stress_ex_ante = only information known at signal date
    stress_realized = includes future movement for diagnosis

## What to do next

First priority is not adding random new features. First priority is cleanup and compact outputs.

Next coding steps:

1. Add visuals/summarize_market_fabric_clusters.py.
2. Generate cluster_identity_summary.csv from cluster_summary.csv.
3. Add human-readable cluster names.
4. Patch visualizer so cluster labels can display names.
5. Split stress into stress_ex_ante and stress_realized.
6. Improve MP4/export workflow.
7. Add visual Monte Carlo comparison.
8. Move heavy repeated work into Rust or compact vectorized backends.

## Important warning

The market graph fabric is visually successful, but it should not become another source of uncontrolled output bloat.

Future graph fabric builds should eventually write:

    manifest.json
    frame_summary.csv
    cluster_summary.csv
    frames.zarr or frames.npz

instead of hundreds or thousands of individual frame files.
