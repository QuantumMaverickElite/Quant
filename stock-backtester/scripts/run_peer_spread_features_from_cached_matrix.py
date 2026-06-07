# scripts/run_peer_spread_features_from_cached_matrix.py

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build peer-spread features directly from cached price/return matrices."
    )

    p.add_argument(
        "--prices-meta",
        default="outputs/cache/matrices/h100_market_common_stock_only_v3/prices_meta.json",
    )
    p.add_argument(
        "--returns-meta",
        default="outputs/cache/returns/h100_market_common_stock_only_v3_clipped/returns_meta.json",
    )
    p.add_argument(
        "--out",
        default="outputs/correlation/peer_spreads_market_common_stock_only_v3.parquet",
    )
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default=None)
    p.add_argument("--corr-window", type=int, default=120)
    p.add_argument("--z-window", type=int, default=60)
    p.add_argument("--step", type=int, default=5)
    p.add_argument("--horizons", type=int, nargs="+", default=[5, 20, 100])
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument(
        "--max-tickers",
        type=int,
        default=0,
        help="Optional cap for smoke tests. 0 means all tickers.",
    )
    p.add_argument(
        "--min-valid-return-coverage",
        type=float,
        default=0.80,
    )
    p.add_argument(
        "--min-valid-price-coverage",
        type=float,
        default=0.80,
    )
    p.add_argument(
        "--dtype",
        default="float32",
        choices=["float32", "float64"],
    )

    return p.parse_args()


def load_matrix(meta_path: str) -> tuple[np.ndarray, list[str], pd.DatetimeIndex, dict]:
    path = Path(meta_path)
    meta = json.loads(path.read_text())

    dtype = np.float32 if meta.get("dtype", "float32") == "float32" else np.float64
    raw = np.fromfile(path.parent / meta["binary_file"], dtype=dtype)
    arr = raw.reshape(int(meta["rows"]), int(meta["cols"]))

    tickers = meta.get("tickers") or meta.get("columns")
    dates = pd.to_datetime(meta.get("dates") or meta.get("index"))

    if tickers is None or dates is None:
        raise ValueError(f"Missing tickers/dates in {meta_path}. Keys: {list(meta.keys())}")

    return arr, list(tickers), pd.DatetimeIndex(dates), meta


def normalize_rows(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32, copy=True)
    x[~np.isfinite(x)] = np.nan

    mu = np.nanmean(x, axis=0, keepdims=True)
    sig = np.nanstd(x, axis=0, keepdims=True)

    sig = np.where(np.isfinite(sig) & (sig > 1e-8), sig, np.nan)
    z = (x - mu) / sig
    z[~np.isfinite(z)] = 0.0
    return z.astype(np.float32)


def corr_from_window(window: np.ndarray) -> np.ndarray:
    z = normalize_rows(window)
    denom = max(1, z.shape[0] - 1)
    corr = (z.T @ z) / float(denom)
    corr = np.clip(corr, -1.0, 1.0).astype(np.float32)
    np.fill_diagonal(corr, -np.inf)
    return corr


def topk_peer_indices(corr: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
    n = corr.shape[0]
    k = min(top_k, max(1, n - 1))

    idx = np.argpartition(corr, -k, axis=1)[:, -k:]
    vals = np.take_along_axis(corr, idx, axis=1)

    order = np.argsort(vals, axis=1)[:, ::-1]
    idx = np.take_along_axis(idx, order, axis=1)
    vals = np.take_along_axis(vals, order, axis=1)

    vals = np.where(np.isfinite(vals), vals, np.nan).astype(np.float32)
    return idx.astype(np.int32), vals


def cumulative_return(prices: np.ndarray, t: int, horizon: int) -> np.ndarray:
    start = t - horizon
    if start < 0:
        return np.full(prices.shape[1], np.nan, dtype=np.float32)

    p0 = prices[start].astype(np.float64)
    p1 = prices[t].astype(np.float64)

    out = p1 / p0 - 1.0
    out[~np.isfinite(out)] = np.nan
    return out.astype(np.float32)


def main() -> None:
    args = parse_args()

    prices, price_tickers, price_dates, _ = load_matrix(args.prices_meta)
    returns, return_tickers, return_dates, _ = load_matrix(args.returns_meta)

    if price_tickers != return_tickers:
        common = sorted(set(price_tickers).intersection(return_tickers))
        price_pos = {t: i for i, t in enumerate(price_tickers)}
        return_pos = {t: i for i, t in enumerate(return_tickers)}
        price_idx = [price_pos[t] for t in common]
        return_idx = [return_pos[t] for t in common]

        prices = prices[:, price_idx]
        returns = returns[:, return_idx]
        tickers = common
    else:
        tickers = price_tickers

    # Align dates by common dates.
    price_date_pos = {d: i for i, d in enumerate(price_dates)}
    return_date_pos = {d: i for i, d in enumerate(return_dates)}
    common_dates = [d for d in return_dates if d in price_date_pos]

    price_rows = [price_date_pos[d] for d in common_dates]
    return_rows = [return_date_pos[d] for d in common_dates]

    prices = prices[price_rows]
    returns = returns[return_rows]
    dates = pd.DatetimeIndex(common_dates)

    if args.max_tickers and args.max_tickers > 0:
        tickers = tickers[: args.max_tickers]
        prices = prices[:, : args.max_tickers]
        returns = returns[:, : args.max_tickers]

    price_cov = np.isfinite(prices).mean(axis=0)
    return_cov = np.isfinite(returns).mean(axis=0)

    keep = (
        (price_cov >= args.min_valid_price_coverage)
        & (return_cov >= args.min_valid_return_coverage)
    )

    tickers = [t for t, ok in zip(tickers, keep) if ok]
    prices = prices[:, keep]
    returns = returns[:, keep]

    start = pd.Timestamp(args.start)
    end = pd.Timestamp(args.end) if args.end else dates.max()

    max_horizon = max(args.horizons)
    first_idx = max(args.corr_window, max_horizon, int(np.searchsorted(dates.values, np.datetime64(start), side="left")))
    last_idx = int(np.searchsorted(dates.values, np.datetime64(end), side="right")) - 1

    check_indices = list(range(first_idx, last_idx + 1, args.step))

    print("=== run_peer_spread_features_from_cached_matrix.py ===")
    print(f"tickers after filters: {len(tickers):,}")
    print(f"dates: {dates.min().date()} -> {dates.max().date()}")
    print(f"check dates: {len(check_indices):,}")
    print(f"corr_window: {args.corr_window}")
    print(f"horizons: {args.horizons}")
    print(f"top_k: {args.top_k}")
    print(f"out: {args.out}")
    print()

    records: list[dict] = []
    n = len(tickers)

    for j, t in enumerate(check_indices):
        d = dates[t]

        w0 = t - args.corr_window + 1
        window = returns[w0 : t + 1]

        valid_in_window = np.isfinite(window).mean(axis=0) >= args.min_valid_return_coverage
        if valid_in_window.sum() < max(10, args.top_k + 2):
            continue

        corr = corr_from_window(window)
        corr[:, ~valid_in_window] = -np.inf
        corr[~valid_in_window, :] = -np.inf

        peer_idx, peer_corr = topk_peer_indices(corr, args.top_k)

        for horizon in args.horizons:
            stock_ret = cumulative_return(prices, t, horizon)

            peer_ret = np.full(n, np.nan, dtype=np.float32)
            top_avg_corr = np.full(n, np.nan, dtype=np.float32)

            for i in range(n):
                if not valid_in_window[i] or not np.isfinite(stock_ret[i]):
                    continue

                peers = peer_idx[i]
                peer_vals = stock_ret[peers]
                peer_corr_vals = peer_corr[i]

                valid_peers = np.isfinite(peer_vals) & np.isfinite(peer_corr_vals)

                if valid_peers.sum() < max(2, min(args.top_k, 3)):
                    continue

                peer_ret[i] = float(np.nanmean(peer_vals[valid_peers]))
                top_avg_corr[i] = float(np.nanmean(peer_corr_vals[valid_peers]))

            spread = stock_ret - peer_ret

            for i, ticker in enumerate(tickers):
                if not np.isfinite(spread[i]):
                    continue

                peers = [tickers[int(p)] for p in peer_idx[i][: args.top_k]]

                rec = {
                    "date": d,
                    "ticker": ticker,
                    "window": args.corr_window,
                    "horizon": horizon,
                    "stock_return": float(stock_ret[i]),
                    "peer_basket_return": float(peer_ret[i]),
                    "peer_spread": float(spread[i]),
                    "top_k_avg_corr": float(top_avg_corr[i]) if np.isfinite(top_avg_corr[i]) else np.nan,
                }

                for k, peer in enumerate(peers, start=1):
                    rec[f"peer_{k}"] = peer

                records.append(rec)

        if j % 10 == 0 or j == len(check_indices) - 1:
            print(f"[{j + 1:04d}/{len(check_indices):04d}] {d.date()} records={len(records):,}")

    df = pd.DataFrame(records)

    if df.empty:
        raise SystemExit("No peer-spread records produced.")

    df = df.sort_values(["ticker", "horizon", "date"]).reset_index(drop=True)

    # Rolling z-score by ticker/horizon.
    grouped = df.groupby(["ticker", "horizon"], group_keys=False)

    roll_mean = grouped["peer_spread"].transform(
        lambda s: s.rolling(args.z_window, min_periods=max(10, args.z_window // 3)).mean()
    )
    roll_std = grouped["peer_spread"].transform(
        lambda s: s.rolling(args.z_window, min_periods=max(10, args.z_window // 3)).std()
    )

    df["peer_spread_z"] = (df["peer_spread"] - roll_mean) / roll_std
    df["peer_spread_z"] = df["peer_spread_z"].replace([np.inf, -np.inf], np.nan)

    df = df[df["peer_spread_z"].notna()].copy()

    # Reorder to match older pipeline.
    preferred = [
        "date",
        "ticker",
        "window",
        "horizon",
        "stock_return",
        "peer_basket_return",
        "peer_spread",
        "peer_spread_z",
        "top_k_avg_corr",
    ] + [f"peer_{i}" for i in range(1, args.top_k + 1)]

    existing = [c for c in preferred if c in df.columns]
    remaining = [c for c in df.columns if c not in existing]
    df = df[existing + remaining].sort_values(["date", "ticker", "horizon"])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)

    print()
    print(f"Saved peer spreads: {len(df):,} rows -> {out}")
    print("Unique tickers:", df["ticker"].nunique())
    print("Date range:", df["date"].min(), "->", df["date"].max())
    print("Horizon counts:")
    print(df["horizon"].value_counts().sort_index().to_string())
    print()
    print(df.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
