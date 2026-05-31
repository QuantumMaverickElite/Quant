# CPU/GPU Matrix Backend

The project now includes experimental CPU/GPU matrix infrastructure.

## Files

```text
src/backtester/engines/array_backend.py
src/backtester/engines/matrix_batch_ops.py
scripts/benchmark_array_backend.py
scripts/benchmark_matrix_batch_ops.py
```

## Array Backend

`array_backend.py` selects either NumPy or CuPy through a common interface.

```text
backend="numpy" -> CPU arrays
backend="cupy"  -> NVIDIA CUDA arrays
```

This prevents backend-specific logic from spreading throughout the project.

## Matrix Batch Ops

`matrix_batch_ops.py` contains reusable matrix operations:

```text
compute_return_matrix
cross_sectional_rank_desc
top_n_mask_from_scores
equal_weight_from_mask
portfolio_returns_from_weights
equity_curve_from_returns
```

This file is the math-kernel layer, not the final allocator.

## Hybrid Philosophy

The correct architecture is hybrid:

```text
CPU:
    dates
    orchestration
    branching logic
    logging
    experiment control

GPU:
    large return matrices
    signal matrices
    top-N masks
    weight matrices
    portfolio return matrices
    batch portfolio evaluation
```

## Benchmark Lesson

Small universes favor CPU because GPU overhead dominates.

Large matrix workloads favor GPU.

The project should not force GPU into every script. GPU should be used only where matrix scale justifies it.

## Important Rule

Avoid repeated CPU/GPU transfers.

Good:

```text
CPU -> GPU once
GPU does large batch
CPU receives compact summary
```

Bad:

```text
CPU -> GPU -> CPU -> GPU every date
```
