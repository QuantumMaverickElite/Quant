from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ReturnMatrix:
    """
    Matrix-shaped return data.

    values:
        Shape (T, N), where T = dates and N = assets.

    dates:
        Length T.

    tickers:
        Length N.
    """

    values: np.ndarray
    dates: pd.DatetimeIndex
    tickers: Sequence[str]

    def validate(self) -> None:
        if self.values.ndim != 2:
            raise ValueError("ReturnMatrix.values must be 2D with shape (T, N).")

        t, n = self.values.shape

        if len(self.dates) != t:
            raise ValueError(
                f"dates length mismatch: got {len(self.dates)}, expected {t}."
            )

        if len(self.tickers) != n:
            raise ValueError(
                f"tickers length mismatch: got {len(self.tickers)}, expected {n}."
            )


@dataclass(frozen=True)
class AssetMetadata:
    """
    Asset classification data aligned to ReturnMatrix.tickers.

    sector_codes and industry_codes should be integer arrays of length N.
    Unknown/missing groups can use -1.
    """

    tickers: Sequence[str]
    sector_codes: np.ndarray
    industry_codes: np.ndarray

    def validate(self) -> None:
        n = len(self.tickers)

        if self.sector_codes.shape != (n,):
            raise ValueError("sector_codes must have shape (N,).")

        if self.industry_codes.shape != (n,):
            raise ValueError("industry_codes must have shape (N,).")
