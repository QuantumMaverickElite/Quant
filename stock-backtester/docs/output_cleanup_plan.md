# Output Cleanup Plan

The project must stay disk-clean for hygiene, speed, and hardware longevity.

The problem is not source code size. The problem is generated experiment output.

Current major disk pressure areas observed after cleanup:

    outputs/monte_carlo          about 1.2G
    outputs/threshold_rebalance  about 421M
    outputs/signals              about 229M
    outputs/rust_stress          about 81M

The visual plot folder was already reduced by deleting duplicate generated fabric runs and keeping the final KMeans long/short run.

## Philosophy

Default behavior should be compact.

Scripts should not save large per-run curves, plots, frame folders, or per-trial CSVs unless explicitly requested.

Good default:

    summary.csv
    summary.parquet
    manifest.json
    small diagnostic report

Only save heavy artifacts when a flag is passed:

    --save-curves
    --save-plots
    --save-trials
    --save-frames
    --save-debug

## Keep / Delete / Archive rules

### Keep

Keep source code, docs, final signal files, final scorecards, final summaries, and reproducible manifests.

Examples:

    outputs/signals/large_universe_peer_spread_long_short_top5_v1.parquet
    outputs/context/market_context.parquet
    outputs/reports/*scorecard*
    outputs/research/*scorecard*
    outputs/reports/plots/market_graph_fabric_2020_long_short_cluster_ring_full_kmeans

### Delete

Delete smoke runs, duplicate visual runs, temporary debug outputs, repeated curve folders, and old one-off plots.

Examples:

    outputs/reports/plots/*smoke*
    outputs/reports/plots/*test*
    old market_graph_fabric_* variants except final preserved run
    repeated spaghetti folders
    repeated threshold paired curve folders once summarized

### Archive

Archive only if the output is historically useful but not active.

Archive target:

    archive/generated_outputs/

Archive should still be compact. Prefer compressed summaries over raw large folders.

## Cleanup order

1. outputs/monte_carlo
2. outputs/threshold_rebalance
3. outputs/rust_stress
4. outputs/reports/plots
5. archive/old_backtests
6. outputs/signals only after a signal manifest exists

Do not aggressively delete outputs/signals until a manifest identifies which files are final, derived, duplicate, or obsolete.

## Immediate next cleanup targets

### outputs/monte_carlo

This is the largest folder.

Likely cleanup:

    remove old curve-heavy runs
    remove repeated plots
    keep monte_carlo_summary.csv
    keep risk stats and benchmark comparison summaries
    delete monte_carlo_equity_curves.csv unless explicitly final
    delete spaghetti plots unless explicitly final

### outputs/threshold_rebalance

Biggest folders are paired curve outputs.

Likely cleanup:

    weekly_check_sample24_port12_paired_curves_v1
    weekly_check_sample24_port8_paired_curves_v1
    weekly_check_sample24_port5_paired_curves_v1

These are around 100M each and should be compressed, summarized, or deleted if not final.

### outputs/rust_stress

Keep final strategy stress runs and summary files. Delete sanity/smoke folders once code is committed and tests are documented.

Possible keepers:

    peer_spread_top5_no_restricted_h60_v1_20k
    peer_spread_short_top5_h20_v1_20k
    final no-restricted subperiod summaries
    top winner exclusion summaries
    year exclusion summaries

Possible deletions after review:

    smoke_long_direction_patch
    sanity_long_short_direction
    sanity_losing_short_direction
    duplicate h100 experiments

## Required script changes

Monte Carlo and threshold scripts should add compact-output options.

Needed flags:

    --compact
    --save-curves
    --save-plots
    --save-trials
    --save-debug
    --out-dir

Default should be:

    compact = true
    save curves = false
    save plots = false
    save trials = false

## Preferred future output structure

For experiments:

    outputs/experiments/<experiment_name>/
        manifest.json
        summary.csv
        summary.parquet
        notes.md

For heavy visual frames:

    outputs/reports/plots/<run_name>/
        manifest.json
        frame_summary.csv
        cluster_summary.csv
        frames.zarr

For Monte Carlo:

    outputs/monte_carlo/<run_name>/
        manifest.json
        monte_carlo_summary.csv
        risk_stats.csv
        benchmark_comparison.csv

Only save:

    monte_carlo_trials.csv
    monte_carlo_equity_curves.csv
    plots/

when explicitly requested.

## Quick disk audit commands

Check top output folders:

    du -h -d 1 outputs | sort -h

Check plot folders:

    du -h -d 1 outputs/reports/plots | sort -h | tail -30

Check Monte Carlo folders:

    du -h -d 1 outputs/monte_carlo | sort -h | tail -30

Check threshold folders:

    du -h -d 1 outputs/threshold_rebalance | sort -h | tail -30

Check Rust stress folders:

    du -h -d 1 outputs/rust_stress | sort -h | tail -30

Remove Python caches:

    find . -type d -name "__pycache__" -prune -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete

## Long-term storage goal

The project should be able to run large experiments without destroying laptop storage.

The long-term goal is:

    fewer files
    fewer CSVs
    more Parquet/Zstd
    compact summaries by default
    large artifacts only on request
    temporary matrices in /tmp/quant_*
    Rust/GPU for repeated heavy computation
