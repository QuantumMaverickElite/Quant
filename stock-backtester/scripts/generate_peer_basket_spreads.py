# scripts/generate_peer_basket_spreads.py

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate large-universe peer-basket spread features from returns and peer maps."
    )

    parser.add_argument("--returns-meta", required=True, help="Path to returns_meta.json.")
    parser.add_argument("--peers", required=True, help="Path to peers.parquet or peers.csv.")
    parser.add_argument("--out", required=True, help="Output parquet/csv path.")

    parser.add_argument("--spread-window", type=int, default=100)
    parser.add_argument(
        "--min-spread-observations",
        type=int,
        default=80,
        help="Minimum valid relative-return observations required inside the rolling spread window.",
    )
    parser.add_argument("--min-peer-corr", type=float, default=0.30)
    parser.add_argument("--min-avg-peer-corr", type=float, default=0.35)
    parser.add_argument("--min-peer-count", type=int, default=3)
    parser.add_argument(
        "--min-daily-valid-peers",
        type=int,
        default=3,
        help="Minimum peers with finite returns required on a date.",
    )
    parser.add_argument("--max-peers", type=int, default=10)
    parser.add_argument("--weighting", choices=["equal", "corr"], default="equal")
    parser.add_argument("--min-abs-z", type=float, default=0.0)
    parser.add_argument("--long-only-candidates", action="store_true")
    parser.add_argument("--long-z", type=float, default=-2.0)
    parser.add_argument("--horizon", type=int, default=100)

    parser.add_argument(
        "--save-all-rows",
        action="store_true",
        help="Save all valid z-score rows. By default, only rows passing filters are saved if --min-abs-z or --long-only-candidates are used.",
    )

    return parser.parse_args()


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


def cumulative_spread_from_valid_relative(relative_return: np.ndarray, valid: np.ndarray) -> np.ndarray:
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

    direction = np.where(peer_spread_z < 0, "long", "short_or_avoid")
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


def main() -> None:
    args = parse_args()

    returns_meta_path = Path(args.returns_meta)
    peers_path = Path(args.peers)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 80)
    print("Large-Universe Peer-Basket Spread Generation")
    print("=" * 80)

    returns, meta = load_returns(returns_meta_path)
    tickers = [str(t).upper() for t in meta["tickers"]]
    dates = list(meta["dates"])

    if len(dates) != returns.shape[0]:
        raise RuntimeError(f"Date count mismatch: {len(dates)} dates, {returns.shape[0]} return rows.")

    print(f"Returns matrix: {returns.shape[0]:,} rows x {returns.shape[1]:,} tickers")
    print(f"Returns meta: {returns_meta_path}")

    peers = load_peers(peers_path)
    print(f"Peer rows loaded: {len(peers):,}")

    ticker_to_idx = {ticker: i for i, ticker in enumerate(tickers)}

    peers = peers[
        peers["ticker"].isin(ticker_to_idx)
        & peers["peer"].isin(ticker_to_idx)
    ].copy()

    peers["ticker_idx"] = peers["ticker"].map(ticker_to_idx).astype(int)
    peers["peer_idx"] = peers["peer"].map(ticker_to_idx).astype(int)

    peer_map = build_peer_map(
        peers,
        ticker_to_idx,
        min_peer_corr=args.min_peer_corr,
        max_peers=args.max_peers,
    )

    print(f"Tickers with usable peer groups: {len(peer_map):,}")
    print(f"min_peer_corr={args.min_peer_corr:.4f}")
    print(f"min_avg_peer_corr={args.min_avg_peer_corr:.4f}")
    print(f"min_peer_count={args.min_peer_count}")
    print(f"min_daily_valid_peers={args.min_daily_valid_peers}")
    print(f"spread_window={args.spread_window}")
    print(f"min_spread_observations={args.min_spread_observations}")
    print(f"weighting={args.weighting}")

    frames: list[pd.DataFrame] = []

    for n, (ticker, group) in enumerate(peer_map.items(), start=1):
        ticker_idx = ticker_to_idx[ticker]

        out = compute_one_ticker(
            ticker,
            ticker_idx,
            group,
            returns,
            dates,
            spread_window=args.spread_window,
            min_spread_observations=args.min_spread_observations,
            weighting=args.weighting,
            min_avg_peer_corr=args.min_avg_peer_corr,
            min_peer_count=args.min_peer_count,
            min_daily_valid_peers=args.min_daily_valid_peers,
            horizon=args.horizon,
        )

        if out is not None and not out.empty:
            frames.append(out)

        if n % 250 == 0 or n == len(peer_map):
            print(f"Processed {n:,}/{len(peer_map):,} peer groups")

    if frames:
        result = pd.concat(frames, ignore_index=True)
    else:
        result = pd.DataFrame()

    if not result.empty:
        if args.long_only_candidates:
            result = result[result["peer_spread_z"] <= args.long_z].copy()

        if args.min_abs_z > 0:
            result = result[np.abs(result["peer_spread_z"]) >= args.min_abs_z].copy()

        result = result.sort_values(["date", "raw_confidence"], ascending=[True, False])
        result = result.reset_index(drop=True)

    if out_path.suffix.lower() == ".parquet":
        result.to_parquet(out_path, index=False)
    elif out_path.suffix.lower() == ".csv":
        result.to_csv(out_path, index=False)
    else:
        raise ValueError("Output path must end in .parquet or .csv")

    print()
    print("=" * 80)
    print("Peer-basket spread export complete")
    print("=" * 80)
    print(f"Saved: {out_path}")
    print(f"Rows: {len(result):,}")
    print(f"Unique tickers: {result['ticker'].nunique() if not result.empty else 0:,}")

    if not result.empty:
        print()
        print("Most extreme negative z-scores:")
        print(result.sort_values("peer_spread_z").head(20).to_string(index=False))

        print()
        print("Most extreme positive z-scores:")
        print(result.sort_values("peer_spread_z", ascending=False).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
