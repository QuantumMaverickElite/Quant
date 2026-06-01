# src/backtester/correlation/tracker.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd

from backtester.correlation.backend import get_array_module
from backtester.correlation.features import (
    average_corr_to_group,
    average_corr_to_market,
    to_numpy,
    top_k_peers,
    window_corr_matrix,
)
from backtester.correlation.types import AssetMetadata, ReturnMatrix


@dataclass(frozen=True)
class CorrelationTrackerConfig:
    windows: Sequence[int] = (20, 60, 120)
    step: int = 5
    top_k: int = 5
    backend: str = "numpy"


class CorrelationTracker:
    """
    Matrix-first rolling correlation feature generator.

    This is intentionally built as infrastructure, not as a trading strategy.
    """

    def __init__(self, config: CorrelationTrackerConfig | None = None) -> None:
        self.config = config or CorrelationTrackerConfig()

    def compute_features(
        self,
        returns: ReturnMatrix,
        metadata: AssetMetadata,
    ) -> pd.DataFrame:
        returns.validate()
        metadata.validate()

        if list(returns.tickers) != list(metadata.tickers):
            raise ValueError(
                "ReturnMatrix.tickers and AssetMetadata.tickers must align."
            )

        xp = get_array_module(self.config.backend)

        values = xp.asarray(returns.values, dtype=xp.float32)
        sector_codes = xp.asarray(metadata.sector_codes, dtype=xp.int32)
        industry_codes = xp.asarray(metadata.industry_codes, dtype=xp.int32)

        records: list[pd.DataFrame] = []

        for window in self.config.windows:
            if window < 2:
                raise ValueError("All windows must be at least 2.")

            if window > values.shape[0]:
                continue

            for end_idx in range(window, values.shape[0] + 1, self.config.step):
                date = returns.dates[end_idx - 1]
                window_values = values[end_idx - window : end_idx]

                corr = window_corr_matrix(window_values, xp=xp)

                market_corr = average_corr_to_market(corr, xp=xp)
                sector_corr = average_corr_to_group(
                    corr,
                    group_codes=sector_codes,
                    xp=xp,
                    exclude_self=True,
                )
                industry_corr = average_corr_to_group(
                    corr,
                    group_codes=industry_codes,
                    xp=xp,
                    exclude_self=True,
                )

                peer_indices, peer_corrs = top_k_peers(
                    corr,
                    xp=xp,
                    k=self.config.top_k,
                )

                frame = self._build_feature_frame(
                    date=date,
                    window=window,
                    tickers=returns.tickers,
                    market_corr=to_numpy(market_corr),
                    sector_corr=to_numpy(sector_corr),
                    industry_corr=to_numpy(industry_corr),
                    peer_indices=to_numpy(peer_indices),
                    peer_corrs=to_numpy(peer_corrs),
                    tickers_lookup=list(returns.tickers),
                )

                records.append(frame)

        if not records:
            return pd.DataFrame()

        return pd.concat(records, ignore_index=True)

    def _build_feature_frame(
        self,
        date: pd.Timestamp,
        window: int,
        tickers: Sequence[str],
        market_corr: np.ndarray,
        sector_corr: np.ndarray,
        industry_corr: np.ndarray,
        peer_indices: np.ndarray,
        peer_corrs: np.ndarray,
        tickers_lookup: list[str],
    ) -> pd.DataFrame:
        data: dict[str, object] = {
            "date": date,
            "ticker": list(tickers),
            "window": window,
            "market_corr": market_corr.astype(np.float32),
            "sector_corr": sector_corr.astype(np.float32),
            "industry_corr": industry_corr.astype(np.float32),
            "top_k_avg_corr": np.nanmean(peer_corrs, axis=1).astype(np.float32),
        }

        for i in range(peer_indices.shape[1]):
            data[f"peer_{i + 1}"] = [
                tickers_lookup[idx] if idx >= 0 else None for idx in peer_indices[:, i]
            ]
            data[f"peer_{i + 1}_corr"] = peer_corrs[:, i].astype(np.float32)

        return pd.DataFrame(data)
