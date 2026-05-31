# Benchmark Scripts

Benchmark scripts are used to test CPU/GPU performance and matrix scalability.

## Backend Benchmark

```text
scripts/benchmark_array_backend.py
```

Example:

```bash
python scripts/benchmark_array_backend.py \
  --backend numpy \
  --repeats 100 \
  --tile-tickers 400 \
  --tile-dates 1

python scripts/benchmark_array_backend.py \
  --backend cupy \
  --repeats 100 \
  --tile-tickers 400 \
  --tile-dates 1
```

## Matrix Batch Ops Benchmark

```text
scripts/benchmark_matrix_batch_ops.py
```

Example:

```bash
python scripts/benchmark_matrix_batch_ops.py \
  --backend numpy \
  --repeats 5 \
  --tile-tickers 400 \
  --tile-dates 1

python scripts/benchmark_matrix_batch_ops.py \
  --backend cupy \
  --repeats 5 \
  --tile-tickers 400 \
  --tile-dates 1
```

## Interpretation

Small universes usually favor CPU.

Large synthetic universes can favor GPU.

The goal is not to prove GPU is always faster. The goal is to learn where GPU becomes useful.
