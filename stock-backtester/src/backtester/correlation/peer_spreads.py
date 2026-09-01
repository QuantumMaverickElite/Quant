"""Staged cached-matrix peer-basket spread implementation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def dtype_from_name(name: str) -> type[np.float32] | type[np.float64]:
    if name == "float32":
        return np.float32
    if name == "float64":
        return np.float64
    raise ValueError(f"Unsupported dtype: {name}")


def load_returns(meta_path: Path) -> tuple[np.ndarray, dict]:
    meta = json.loads(meta_path.read_text())
    dtype = dtype_from_name(meta["dtype"])

    raw = np.fromfile(meta_path.parent / meta["binary_file"], dtype=dtype)

    rows = int(meta["rows"])
    cols = int(meta["cols"])
    expected = rows * cols

    if raw.size != expected:
        raise RuntimeError(f"Returns binary size mismatch: got {raw.size}, expected {expected}.")

    matrix = raw.reshape(rows, cols).astype(np.float32, copy=False)
    return matrix, meta


def load_peers(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        peers = pd.read_parquet(path)
    elif path.suffix.lower() == ".csv":
        peers = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported peer file extension: {path.suffix}")

    required = {"ticker", "peer", "peer_rank", "corr"}
    missing = required - set(peers.columns)
    if missing:
        raise RuntimeError(f"Peer file missing columns: {sorted(missing)}")

    peers = peers.copy()
    peers["ticker"] = peers["ticker"].astype(str).str.upper()
    peers["peer"] = peers["peer"].astype(str).str.upper()
    peers["peer_rank"] = peers["peer_rank"].astype(int)
    peers["corr"] = peers["corr"].astype(float)

    return peers


def rolling_mean_std_count(
    x: np.ndarray,
    valid: np.ndarray,
    window: int,
    min_observations: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if window <= 1:
        raise ValueError("--spread-window must be greater than 1.")

    if min_observations <= 1:
        raise ValueError("--min-spread-observations must be greater than 1.")

    min_periods = min(window, min_observations)

    s = pd.Series(np.where(valid, x, np.nan))
    mean = s.rolling(window=window, min_periods=min_periods).mean().to_numpy()
    std = s.rolling(window=window, min_periods=min_periods).std(ddof=1).to_numpy()
    count = s.rolling(window=window, min_periods=min_periods).count().to_numpy()

    return mean.astype(np.float32), std.astype(np.float32), count.astype(np.float32)


def build_peer_map(
    peers: pd.DataFrame,
    ticker_to_idx: dict[str, int],
    *,
    min_peer_corr: float,
    max_peers: int,
) -> dict[str, pd.DataFrame]:
    frame = peers[
        (peers["ticker"].isin(ticker_to_idx))
        & (peers["peer"].isin(ticker_to_idx))
        & (peers["corr"] >= min_peer_corr)
    ].copy()

    frame = frame.sort_values(["ticker", "peer_rank"], ascending=[True, True])
    frame = frame.groupby("ticker", group_keys=False).head(max_peers).copy()

    return {ticker: group.copy() for ticker, group in frame.groupby("ticker")}


def peer_weights(corrs: np.ndarray, weighting: str) -> np.ndarray:
    if weighting == "equal":
        w = np.ones_like(corrs, dtype=np.float32)
    elif weighting == "corr":
        w = np.maximum(corrs.astype(np.float32), 0.0)
    else:
        raise ValueError(f"Unsupported weighting: {weighting}")

    total = float(w.sum())
    if total <= 0:
        return np.ones_like(corrs, dtype=np.float32) / len(corrs)

    return w / total


def cumulative_spread_from_valid_relative(
    relative_return: np.ndarray,
    valid: np.ndarray,
) -> np.ndarray:
    spread = np.full(relative_return.shape[0], np.nan, dtype=np.float32)

    if not valid.any():
        return spread

    filled = np.where(valid, relative_return, 0.0).astype(np.float32)
    csum = np.cumsum(filled, dtype=np.float32)

    # Carrying spread through invalid days can create false rolling observations.
    # Keep invalid days as NaN, but valid days retain the cumulative spread level.
    spread[valid] = csum[valid]

    return spread


def compute_one_ticker(
    ticker: str,
    ticker_idx: int,
    peer_group: pd.DataFrame,
    returns: np.ndarray,
    dates: list[str],
    *,
    spread_window: int,
    min_spread_observations: int,
    weighting: str,
    min_avg_peer_corr: float,
    min_peer_count: int,
    min_daily_valid_peers: int,
    horizon: int,
) -> pd.DataFrame | None:
    peer_indices = []
    peer_corrs = []
    peer_names = []

    for row in peer_group.itertuples(index=False):
        peer_indices.append(int(row.peer_idx))
        peer_corrs.append(float(row.corr))
        peer_names.append(str(row.peer))

    if len(peer_indices) < min_peer_count:
        return None

    peer_corrs_arr = np.asarray(peer_corrs, dtype=np.float32)
    avg_peer_corr = float(np.mean(peer_corrs_arr))

    if avg_peer_corr < min_avg_peer_corr:
        return None

    ticker_ret = returns[:, ticker_idx].astype(np.float32, copy=False)
    peer_rets = returns[:, peer_indices].astype(np.float32, copy=False)

    weights = peer_weights(peer_corrs_arr, weighting)

    valid_peer = np.isfinite(peer_rets)
    daily_valid_peer_count = valid_peer.sum(axis=1).astype(np.int16)

    weighted_peer = np.where(valid_peer, peer_rets * weights[None, :], 0.0)
    denom = np.where(valid_peer, weights[None, :], 0.0).sum(axis=1)

    peer_basket_return = np.full(returns.shape[0], np.nan, dtype=np.float32)

    good_peer_day = (denom > 0) & (daily_valid_peer_count >= min_daily_valid_peers)
    peer_basket_return[good_peer_day] = weighted_peer[good_peer_day].sum(axis=1) / denom[good_peer_day]

    valid_ticker = np.isfinite(ticker_ret)
    valid_relative = valid_ticker & np.isfinite(peer_basket_return)

    relative_return = np.full(returns.shape[0], np.nan, dtype=np.float32)
    relative_return[valid_relative] = ticker_ret[valid_relative] - peer_basket_return[valid_relative]

    spread = cumulative_spread_from_valid_relative(relative_return, valid_relative)

    spread_mean, spread_std, spread_obs = rolling_mean_std_count(
        spread,
        valid_relative,
        spread_window,
        min_spread_observations,
    )

    peer_spread_z = np.full_like(spread, np.nan, dtype=np.float32)
    z_valid = (
        valid_relative
        & np.isfinite(spread_mean)
        & np.isfinite(spread_std)
        & (spread_std > 1e-12)
        & (spread_obs >= min_spread_observations)
    )
    peer_spread_z[z_valid] = (spread[z_valid] - spread_mean[z_valid]) / spread_std[z_valid]

    direction = np.where(peer_spread_z < 0, "long", "short")
    raw_confidence = np.abs(peer_spread_z) * avg_peer_corr

    out = pd.DataFrame(
        {
            "date": dates,
            "ticker": ticker,
            "horizon": int(horizon),
            "peer_count": int(len(peer_indices)),
            "daily_valid_peer_count": daily_valid_peer_count,
            "avg_peer_corr": avg_peer_corr,
            "peer_list": "|".join(peer_names),
            "peer_corr_list": "|".join(f"{c:.6f}" for c in peer_corrs),
            "ticker_return": ticker_ret,
            "peer_basket_return": peer_basket_return,
            "relative_return": relative_return,
            "spread": spread,
            "spread_mean": spread_mean,
            "spread_std": spread_std,
            "spread_obs": spread_obs,
            "peer_spread_z": peer_spread_z,
            "direction": direction,
            "raw_confidence": raw_confidence,
        }
    )

    out = out[np.isfinite(out["peer_spread_z"])].copy()
    if out.empty:
        return None

    return out


def filter_spread_candidates(
    result: pd.DataFrame,
    *,
    min_abs_z: float,
    side: str,
    long_only_candidates: bool,
    long_z: float,
) -> pd.DataFrame:
    """Apply the staged command's historical tail and ordering rules."""
    if result.empty:
        return result

    min_abs_z = abs(float(min_abs_z))

    if long_only_candidates and side != "long":
        raise ValueError("--long-only-candidates is only compatible with --side long.")

    if long_only_candidates:
        min_abs_z = max(min_abs_z, abs(float(long_z)))

    if min_abs_z > 0:
        if side == "long":
            result = result[result["peer_spread_z"] <= -min_abs_z].copy()
            result["direction"] = "long"

        elif side == "short":
            result = result[result["peer_spread_z"] >= min_abs_z].copy()
            result["direction"] = "short"

        elif side == "both":
            long = result[result["peer_spread_z"] <= -min_abs_z].copy()
            long["direction"] = "long"

            short = result[result["peer_spread_z"] >= min_abs_z].copy()
            short["direction"] = "short"

            result = pd.concat([long, short], ignore_index=True)

    else:
        if side == "long":
            result = result[result["peer_spread_z"] < 0].copy()
            result["direction"] = "long"

        elif side == "short":
            result = result[result["peer_spread_z"] > 0].copy()
            result["direction"] = "short"

        elif side == "both":
            result = result[result["peer_spread_z"] != 0].copy()
            result["direction"] = np.where(result["peer_spread_z"] < 0, "long", "short")

    sort_cols = ["date", "raw_confidence"]
    result = result.sort_values(sort_cols, ascending=[True, False])
    return result.reset_index(drop=True)
