# Matrix Allocator Engine

The matrix allocator engine moves allocator simulation toward a more scalable structure.

## File

```text
src/backtester/engines/matrix_allocator_engine.py
```

## Runner

```text
scripts/threshold_rebalance_matrix_engine.py
```

## Purpose

The matrix engine is meant to separate allocator logic from one-off scripts.

It supports the same threshold rebalance research while moving the project toward reusable, matrix-oriented simulation.

## Example

```bash
python scripts/threshold_rebalance_matrix_engine.py \
  --runs 1000 \
  --sample-size 24 \
  --portfolio-size 8 \
  --thresholds 0.00 0.01 0.03 0.05 0.075 0.10 0.15 0.20 \
  --save-mode none \
  --workers 4 \
  --progress-every 100
```

## Multiprocessing

The matrix threshold runner supports CPU multiprocessing with `--workers`.

For the current small universe, CPU multiprocessing is very effective.

## Current Role

This engine is not the final allocator.

It is the bridge between older scripts and the future allocator architecture.
