from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ArrayBackend:
    name: str
    xp: Any
    is_gpu: bool

    def asarray(self, x: Any, dtype: Any | None = None) -> Any:
        return self.xp.asarray(x, dtype=dtype)

    def to_cpu(self, x: Any) -> np.ndarray:
        if not self.is_gpu:
            return np.asarray(x)
        return self.xp.asnumpy(x)

    def synchronize(self) -> None:
        if self.is_gpu:
            self.xp.cuda.Stream.null.synchronize()


def get_backend(name: str) -> ArrayBackend:
    normalized = name.lower().strip()

    if normalized == "numpy":
        return ArrayBackend(name="numpy", xp=np, is_gpu=False)

    if normalized == "cupy":
        try:
            import cupy as cp
        except Exception as exc:
            raise RuntimeError(
                "CuPy backend requested, but CuPy could not be imported."
            ) from exc

        return ArrayBackend(name="cupy", xp=cp, is_gpu=True)

    raise ValueError(f"Unknown backend: {name}. Expected 'numpy' or 'cupy'.")
