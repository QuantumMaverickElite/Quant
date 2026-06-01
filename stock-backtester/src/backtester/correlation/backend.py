# src/backtester/correlation/backend.py

from __future__ import annotations

from typing import Any


def get_array_module(backend: str = "numpy") -> Any:
    """
    Return the array module for the requested backend.

    backend:
        "numpy" -> NumPy CPU backend
        "cupy"  -> CuPy GPU backend

    This keeps the compute code backend-agnostic.
    """

    backend = backend.lower().strip()

    if backend == "numpy":
        import numpy as np

        return np

    if backend == "cupy":
        try:
            import cupy as cp

            return cp
        except ImportError as exc:
            raise ImportError(
                "CuPy backend requested, but cupy is not installed."
            ) from exc

    raise ValueError(f"Unsupported backend: {backend}")
