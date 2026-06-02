#!/usr/bin/env python3
"""
build_market_graph_frames.py
============================

Whole-market graph/fabric frame builder.

Visual model:
    stock node       = fabric vertex
    rolling corr     = fabric stitching / spring strength
    top-k corr edges  = visible mesh links
    x/y position     = rolling correlation geometry
    z height         = selected market/signal metric
    node color       = selected heat metric
    corr delta       = fabric tension / twisting signal

This script does heavy work offline and writes cached frames for a lightweight
visualizer to play later.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import cupy as cp  # type: ignore
    HAS_CUPY = True
except Exception:
    cp = None
    HAS_CUPY = False


try:
    from scipy.sparse.linalg import eigsh  # type: ignore
    HAS_SCIPY_EIGSH = True
except Exception:
    eigsh = None
    HAS_SCIPY_EIGSH = False


try:
    from sklearn.cluster import KMeans  # type: ignore
    HAS_SKLEARN_CLUSTER = True
except Exception:
    KMeans = None
    HAS_SKLEARN_CLUSTER = False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build whole-market rolling-correlation graph/fabric frames.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--returns-meta", required=True)
    p.add_argument("--signals", required=True)
    p.add_argument("--context", default=None)
    p.add_argument("--out-dir", required=True)

    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    p.add_argument("--frame-step-days", type=int, default=5)
    p.add_argument("--lookback", type=int, default=126)
    p.add_argument("--forward-days", type=int, default=60)

    p.add_argument("--max-nodes", type=int, default=1000)
    p.add_argument("--top-signal-nodes", type=int, default=20)
    p.add_argument("--extra-signal-neighborhood", type=int, default=250)
    p.add_argument("--extra-random-nodes", type=int, default=250)
    p.add_argument("--extra-volatile-nodes", type=int, default=250)

    p.add_argument("--top-k-edges", type=int, default=8)
    p.add_argument("--min-edge-corr", type=float, default=0.35)
    p.add_argument("--max-edges", type=int, default=20000)

    p.add_argument(
        "--layout-mode",
        choices=["mds", "sector-ring"],
        default="mds",
        help="sector-ring is reserved for sector metadata later; currently uses MDS.",
    )
    p.add_argument(
        "--layout-engine",
        choices=["mds", "corr-pca-fast", "cluster-ring"],
        default="corr-pca-fast",
        help="mds is prettier but O(n^3); corr-pca-fast is scalable; cluster-ring creates sector-like continents.",
    )

    p.add_argument("--cluster-count", type=int, default=12)
    p.add_argument(
        "--cluster-anchor-strength",
        type=float,
        default=0.65,
        help="How strongly cluster-ring pulls stocks into cluster continents.",
    )

    p.add_argument(
        "--z-mode",
        choices=["peer_spread_z", "forward_return", "realized_vol", "realized_vol_z", "entropy_proxy", "entropy_z", "confidence", "corr_degree", "stress", "zero"],
        default="peer_spread_z",
    )
    p.add_argument(
        "--color-mode",
        choices=["forward_return", "peer_spread_z", "realized_vol", "realized_vol_z", "entropy_proxy", "entropy_z", "confidence", "corr_degree", "stress"],
        default="forward_return",
    )

    p.add_argument("--use-cupy", action="store_true", help="Use CuPy for correlation when available.")
    p.add_argument("--force-rebuild", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def load_returns(meta_path: Path) -> tuple[np.ndarray, dict]:
    meta = json.loads(meta_path.read_text())
    dtype = np.float32 if meta.get("dtype") == "float32" else np.float64
    arr = np.fromfile(meta_path.parent / meta["binary_file"], dtype=dtype)
    arr = arr.reshape(int(meta["rows"]), int(meta["cols"])).astype(np.float32, copy=False)
    return arr, meta


def normalize_ticker(t: object) -> str:
    return str(t).strip().upper().replace(".", "-")


def load_signals(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path).copy()
    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].map(normalize_ticker)

    if "adjusted_confidence" not in df.columns:
        df["adjusted_confidence"] = df["raw_confidence"] if "raw_confidence" in df.columns else 0.0
    if "peer_spread_z" not in df.columns:
        df["peer_spread_z"] = 0.0
    if "direction" not in df.columns:
        df["direction"] = np.where(df["peer_spread_z"] < 0, "long", "short")
    return df


def load_context(path: str | None) -> pd.DataFrame | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def nearest_prior_date(dates: pd.Series | pd.DatetimeIndex, requested: pd.Timestamp) -> pd.Timestamp | None:
    s = pd.Series(dates).dropna()
    eligible = s[s <= requested]
    if eligible.empty:
        return None
    return pd.Timestamp(eligible.max())


def generate_requested_dates(start: str, end: str, step_days: int) -> list[pd.Timestamp]:
    out = []
    cur = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    while cur <= end_ts:
        out.append(cur)
        cur += pd.Timedelta(days=step_days)
    return out


def clean_window(window: np.ndarray) -> np.ndarray:
    w = window.astype(np.float32, copy=True)
    valid = np.where(np.isfinite(w), w, np.nan)
    with np.errstate(all="ignore"):
        col_means = np.nanmean(valid, axis=0)
    col_means = np.where(np.isfinite(col_means), col_means, 0.0)
    mask = ~np.isfinite(w)
    if mask.any():
        rows, cols = np.where(mask)
        w[rows, cols] = col_means[cols]
    return w


def corrcoef_fast(window: np.ndarray, use_cupy: bool = False) -> np.ndarray:
    w = clean_window(window)

    if use_cupy and HAS_CUPY:
        try:
            x = cp.asarray(w, dtype=cp.float32)
            x = x - cp.mean(x, axis=0, keepdims=True)
            denom = cp.sqrt(cp.sum(x * x, axis=0, keepdims=True))
            denom = cp.maximum(denom, 1e-12)
            x = x / denom
            return cp.asnumpy(x.T @ x).astype(np.float32, copy=False)
        except Exception as e:
            print(f"  [warn] CuPy corr failed; NumPy fallback: {e}")

    x = w - w.mean(axis=0, keepdims=True)
    denom = np.sqrt(np.sum(x * x, axis=0, keepdims=True))
    denom = np.maximum(denom, 1e-12)
    x = x / denom
    return (x.T @ x).astype(np.float32, copy=False)


def classical_mds(corr: np.ndarray, dims: int = 2) -> np.ndarray:
    corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
    corr = np.clip(corr, -0.999, 0.999)
    dist = np.sqrt(np.maximum(0.0, 0.5 * (1.0 - corr))).astype(np.float64)
    dist2 = dist * dist
    n = dist.shape[0]
    center = np.eye(n, dtype=np.float64) - np.ones((n, n), dtype=np.float64) / n
    gram = -0.5 * center @ dist2 @ center
    vals, vecs = np.linalg.eigh(gram)
    order = np.argsort(vals)[::-1]
    vals = np.maximum(vals[order][:dims], 0.0)
    vecs = vecs[:, order][:, :dims]
    return (vecs * np.sqrt(vals + 1e-12)).astype(np.float32)



def corr_pca_fast_layout(corr: np.ndarray) -> np.ndarray:
    """
    Fast correlation-geometry layout.

    This uses the top two eigenvectors of the correlation matrix as x/y
    coordinates. It is less exact than classical MDS, but much faster and
    better suited for 1500-3000+ stock market-fabric frames.

    For large N, scipy.sparse.linalg.eigsh computes only the top components.
    """
    c = np.nan_to_num(corr.astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    c = np.clip(c, -0.999, 0.999)

    # Center so the first component does not merely represent the market mode.
    c = c - c.mean(axis=0, keepdims=True)
    c = c - c.mean(axis=1, keepdims=True)

    n = c.shape[0]

    try:
        if HAS_SCIPY_EIGSH and n >= 300:
            vals, vecs = eigsh(c, k=2, which="LA")
            order = np.argsort(vals)[::-1]
            vals = vals[order]
            vecs = vecs[:, order]
        else:
            vals, vecs = np.linalg.eigh(c)
            order = np.argsort(vals)[::-1][:2]
            vals = vals[order]
            vecs = vecs[:, order]
    except Exception:
        vals, vecs = np.linalg.eigh(c)
        order = np.argsort(vals)[::-1][:2]
        vals = vals[order]
        vecs = vecs[:, order]

    vals = np.maximum(vals, 1e-12)
    coords = vecs * np.sqrt(vals)

    # Normalize to a stable visual range.
    coords = coords.astype(np.float32)
    coords -= coords.mean(axis=0, keepdims=True)
    scale = np.nanpercentile(np.abs(coords), 99)
    if np.isfinite(scale) and scale > 1e-8:
        coords = coords / scale * 0.45

    return coords.astype(np.float32)



def cluster_ring_layout(
    corr: np.ndarray,
    cluster_count: int = 12,
    anchor_strength: float = 0.65,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Cluster-aware market fabric layout.

    This creates sector-like continents without needing official sector data:
      1. compute fast correlation PCA coords
      2. cluster stocks in that geometry
      3. place clusters around a ring
      4. keep local within-cluster geometry

    Returns:
      coords: (n, 2)
      cluster_id: (n,)
    """
    base = corr_pca_fast_layout(corr)
    n = base.shape[0]

    k = int(max(2, min(cluster_count, max(2, n // 20))))

    if HAS_SKLEARN_CLUSTER and KMeans is not None and n >= k:
        try:
            labels = KMeans(n_clusters=k, n_init=5, random_state=42).fit_predict(base)
        except Exception:
            labels = np.arange(n) % k
    else:
        # Fallback: sort by polar angle and split into k groups.
        ang = np.arctan2(base[:, 1], base[:, 0])
        order = np.argsort(ang)
        labels = np.zeros(n, dtype=np.int32)
        chunks = np.array_split(order, k)
        for cid, idx in enumerate(chunks):
            labels[idx] = cid

    labels = labels.astype(np.int32)

    # Order clusters by centroid angle for stable ring placement.
    centroids = np.zeros((k, 2), dtype=np.float32)
    sizes = np.zeros(k, dtype=np.int32)
    for cid in range(k):
        mask = labels == cid
        sizes[cid] = int(mask.sum())
        if mask.any():
            centroids[cid] = base[mask].mean(axis=0)

    order = np.argsort(np.arctan2(centroids[:, 1], centroids[:, 0]))
    rank = {int(cid): i for i, cid in enumerate(order)}

    out = np.zeros_like(base, dtype=np.float32)
    radius = 0.55
    local_scale = 0.28

    for cid in range(k):
        mask = labels == cid
        if not mask.any():
            continue

        r = rank[int(cid)]
        theta = 2.0 * np.pi * r / k
        anchor = np.array([np.cos(theta), np.sin(theta)], dtype=np.float32) * radius

        local = base[mask] - base[mask].mean(axis=0, keepdims=True)
        local_norm = np.nanpercentile(np.abs(local), 95)
        if np.isfinite(local_norm) and local_norm > 1e-8:
            local = local / local_norm * local_scale

        target = anchor + local
        out[mask] = (1.0 - anchor_strength) * base[mask] + anchor_strength * target

    out -= out.mean(axis=0, keepdims=True)
    scale = np.nanpercentile(np.abs(out), 99)
    if np.isfinite(scale) and scale > 1e-8:
        out = out / scale * 0.65

    return out.astype(np.float32), labels.astype(np.int32)


def procrustes_align(coords: np.ndarray, prev: np.ndarray | None) -> np.ndarray:
    if prev is None or prev.shape != coords.shape:
        return coords
    x = coords.astype(np.float64)
    y = prev.astype(np.float64)
    xm = x.mean(axis=0, keepdims=True)
    ym = y.mean(axis=0, keepdims=True)
    x0 = x - xm
    y0 = y - ym
    try:
        u, _, vt = np.linalg.svd(x0.T @ y0)
        return (x0 @ (u @ vt) + ym).astype(np.float32)
    except Exception:
        return coords


def topk_edges(corr: np.ndarray, top_k: int, min_corr: float, max_edges: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = corr.shape[0]
    c = corr.copy()
    np.fill_diagonal(c, -np.inf)
    k = min(max(1, top_k), max(1, n - 1))
    edges: dict[tuple[int, int], float] = {}

    for i in range(n):
        idx = np.argpartition(c[i], -k)[-k:]
        for j in idx:
            val = float(c[i, j])
            if not np.isfinite(val) or val < min_corr:
                continue
            a, b = (i, int(j)) if i < j else (int(j), i)
            if a == b:
                continue
            if (a, b) not in edges or val > edges[(a, b)]:
                edges[(a, b)] = val

    items = sorted(edges.items(), key=lambda kv: kv[1], reverse=True)[:max_edges]
    if not items:
        z = np.zeros(0, dtype=np.uint32)
        return z, z, np.zeros(0, dtype=np.float32)
    return (
        np.array([a for (a, _), _v in items], dtype=np.uint32),
        np.array([b for (_, b), _v in items], dtype=np.uint32),
        np.array([v for _edge, v in items], dtype=np.float32),
    )


def realized_vol(window: np.ndarray) -> np.ndarray:
    with np.errstate(all="ignore"):
        vol = np.nanstd(np.where(np.isfinite(window), window, np.nan), axis=0)
    return np.where(np.isfinite(vol), vol, 0.0).astype(np.float32)


def forward_return(returns: np.ndarray, date_idx: int, node_idx: np.ndarray, forward_days: int) -> np.ndarray:
    start = date_idx + 1
    end = min(returns.shape[0], start + forward_days)
    if start >= end:
        return np.zeros(len(node_idx), dtype=np.float32)
    fut = returns[start:end, :][:, node_idx]
    return np.nansum(np.where(np.isfinite(fut), fut, 0.0), axis=0).astype(np.float32)


def parse_peer_list(value: object) -> list[str]:
    text = str(value)
    if not text or text.lower() == "nan":
        return []
    sep = "|" if "|" in text else "," if "," in text else None
    parts = text.split(sep) if sep else text.split()
    return [normalize_ticker(p) for p in parts if str(p).strip()]


def select_nodes(
    *,
    signals_on_date: pd.DataFrame,
    ticker_to_idx: dict[str, int],
    returns: np.ndarray,
    date_idx: int,
    lookback: int,
    max_nodes: int,
    top_signal_nodes: int,
    extra_signal_neighborhood: int,
    extra_random_nodes: int,
    extra_volatile_nodes: int,
    rng: np.random.Generator,
) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()

    def add(t: object) -> bool:
        tt = normalize_ticker(t)
        if tt in ticker_to_idx and tt not in seen and len(selected) < max_nodes:
            selected.append(tt)
            seen.add(tt)
            return True
        return False

    sig_sorted = signals_on_date.sort_values("adjusted_confidence", ascending=False)

    for _, row in sig_sorted.head(top_signal_nodes).iterrows():
        add(row["ticker"])

    peer_added = 0
    for _, row in sig_sorted.iterrows():
        if peer_added >= extra_signal_neighborhood or len(selected) >= max_nodes:
            break
        for peer in parse_peer_list(row.get("peer_list", "")):
            if add(peer):
                peer_added += 1
                if peer_added >= extra_signal_neighborhood:
                    break

    start_idx = max(0, date_idx - lookback + 1)
    window = returns[start_idx : date_idx + 1, :]
    finite_rate = np.isfinite(window).mean(axis=0)
    with np.errstate(all="ignore"):
        vol = np.nanstd(np.where(np.isfinite(window), window, np.nan), axis=0)
    vol = np.where(np.isfinite(vol), vol, -np.inf)
    candidates = np.where(finite_rate >= 0.80)[0]
    inv = {v: k for k, v in ticker_to_idx.items()}

    if len(candidates):
        order = candidates[np.argsort(vol[candidates])[::-1]]
        for idx in order[: extra_volatile_nodes * 3]:
            if len(selected) >= max_nodes:
                break
            add(inv.get(int(idx), ""))

    if len(candidates):
        rand = candidates.copy()
        rng.shuffle(rand)
        random_added = 0
        for idx in rand:
            if len(selected) >= max_nodes or random_added >= extra_random_nodes:
                break
            if add(inv.get(int(idx), "")):
                random_added += 1

        # Final broad-market fill.
        #
        # The earlier stages intentionally prioritize:
        #   1. active signals
        #   2. signal peer neighborhoods
        #   3. volatile names
        #   4. random market coverage
        #
        # But for whole-market visualization, --max-nodes should actually mean
        # "keep filling until this many valid stocks are included."
        #
        # This turns the graph from a signal island into a real market fabric.
        fill = candidates.copy()
        rng.shuffle(fill)

        for idx in fill:
            if len(selected) >= max_nodes:
                break
            add(inv.get(int(idx), ""))

    return selected


def signal_maps(signals_on_date: pd.DataFrame) -> tuple[dict[str, float], dict[str, float], dict[str, str]]:
    z_map: dict[str, float] = {}
    conf_map: dict[str, float] = {}
    dir_map: dict[str, str] = {}
    for _, row in signals_on_date.sort_values("adjusted_confidence", ascending=False).iterrows():
        t = normalize_ticker(row["ticker"])
        if t in z_map:
            continue
        z_map[t] = float(row.get("peer_spread_z", 0.0))
        conf_map[t] = float(row.get("adjusted_confidence", 0.0))
        dir_map[t] = str(row.get("direction", "long")).lower()
    return z_map, conf_map, dir_map



def robust_zscore(values: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=np.float32)
    finite = np.isfinite(x)

    if finite.sum() < 5:
        return np.zeros_like(x, dtype=np.float32)

    med = np.nanmedian(x[finite])
    mad = np.nanmedian(np.abs(x[finite] - med))
    scale = 1.4826 * mad

    if not np.isfinite(scale) or scale < 1e-8:
        scale = np.nanstd(x[finite])

    if not np.isfinite(scale) or scale < 1e-8:
        return np.zeros_like(x, dtype=np.float32)

    z = (x - med) / scale
    z = np.where(np.isfinite(z), z, 0.0)
    return np.clip(z, -6.0, 6.0).astype(np.float32)



def corr_entropy_proxy(corr: np.ndarray, top_k: int = 30) -> np.ndarray:
    """
    Stock-level graph entropy from rolling correlations.

    Low entropy:
        stock is tied strongly to a small number of peers.

    High entropy:
        stock is diffusely connected across many peers / more regime-confused.

    Returns values roughly in [0, 1].
    """
    c = np.asarray(corr, dtype=np.float32)
    n = c.shape[0]
    out = np.zeros(n, dtype=np.float32)

    if n <= 2:
        return out

    k = min(max(2, top_k), n - 1)

    for i in range(n):
        row = c[i].copy()
        row[i] = 0.0
        row = np.where(np.isfinite(row), row, 0.0)
        row = np.clip(row, 0.0, None)

        if np.all(row <= 0):
            out[i] = 0.0
            continue

        idx = np.argpartition(row, -k)[-k:]
        vals = row[idx]
        total = float(vals.sum())

        if total <= 1e-12:
            out[i] = 0.0
            continue

        p = vals / total
        p = p[p > 1e-12]
        ent = -float(np.sum(p * np.log(p)))
        out[i] = ent / np.log(k)

    return np.clip(out, 0.0, 1.0).astype(np.float32)


def build_node_metrics(
    *,
    tickers: list[str],
    ticker_to_idx: dict[str, int],
    returns: np.ndarray,
    date_idx: int,
    window: np.ndarray,
    signals_on_date: pd.DataFrame,
    forward_days: int,
    corr: np.ndarray,
    z_mode: str,
    color_mode: str,
) -> dict[str, np.ndarray]:
    node_idx = np.array([ticker_to_idx[t] for t in tickers], dtype=np.int32)
    fwd = forward_return(returns, date_idx, node_idx, forward_days)
    vol = realized_vol(window)
    z_map, conf_map, dir_map = signal_maps(signals_on_date)
    peer_z = np.array([z_map.get(t, 0.0) for t in tickers], dtype=np.float32)
    conf = np.array([conf_map.get(t, 0.0) for t in tickers], dtype=np.float32)
    directions = np.array([dir_map.get(t, "") for t in tickers], dtype=object)
    is_long = directions == "long"
    is_short = directions == "short"
    degree = np.nanmean(np.where(np.isfinite(corr), corr, 0.0), axis=1).astype(np.float32)

    # Whole-fabric stress proxy.
    # This is not the final entropy engine yet. It combines:
    #   1. stock-level volatility
    #   2. correlation crowding / fabric tightness
    #   3. large realized forward movement
    vol_z = robust_zscore(vol)
    degree_z = robust_zscore(degree)
    entropy_proxy = corr_entropy_proxy(corr, top_k=30)
    entropy_z = robust_zscore(entropy_proxy)
    abs_fwd_z = robust_zscore(np.abs(fwd))

    # Stress now includes:
    #   volatility heat
    #   correlation crowding / degree
    #   entropy / diffuse connection instability
    #   large realized forward movement
    stress = (
        0.40 * vol_z
        + 0.25 * degree_z
        + 0.25 * entropy_z
        + 0.10 * abs_fwd_z
    ).astype(np.float32)

    metrics = {
        "peer_spread_z": peer_z,
        "forward_return": fwd,
        "realized_vol": vol,
        "realized_vol_z": vol_z,
        "entropy_proxy": entropy_proxy,
        "entropy_z": entropy_z,
        "confidence": conf,
        "corr_degree": degree,
        "stress": stress,
        "zero": np.zeros(len(tickers), dtype=np.float32),
    }
    return {
        "node_idx": node_idx,
        "z": metrics[z_mode].astype(np.float32),
        "color": metrics[color_mode].astype(np.float32),
        "forward_return": fwd.astype(np.float32),
        "realized_vol": vol.astype(np.float32),
        "realized_vol_z": vol_z.astype(np.float32),
        "entropy_proxy": entropy_proxy.astype(np.float32),
        "entropy_z": entropy_z.astype(np.float32),
        "corr_degree": degree.astype(np.float32),
        "stress": stress.astype(np.float32),
        "peer_spread_z": peer_z.astype(np.float32),
        "confidence": conf.astype(np.float32),
        "is_long": is_long.astype(bool),
        "is_short": is_short.astype(bool),
    }


def pct_limits(vals: list[float], lo=1, hi=99) -> tuple[float, float]:
    arr = np.asarray(vals, dtype=np.float32)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return -1.0, 1.0
    a, b = np.percentile(arr, [lo, hi])
    if b <= a:
        b = a + 1e-6
    return float(a), float(b)


def summarize_clusters(
    *,
    frame_id: int,
    snap_date,
    ret_date,
    tickers: list[str],
    cluster_id: np.ndarray,
    metrics: dict[str, np.ndarray],
    max_names: int = 8,
) -> list[dict]:
    rows: list[dict] = []

    if cluster_id is None or len(cluster_id) == 0:
        return rows

    tickers_arr = np.array(tickers, dtype=object)
    conf = metrics.get("confidence", np.zeros(len(tickers), dtype=np.float32))
    stress = metrics.get("stress", np.zeros(len(tickers), dtype=np.float32))
    entropy_z = metrics.get("entropy_z", np.zeros(len(tickers), dtype=np.float32))
    realized_vol_z = metrics.get("realized_vol_z", np.zeros(len(tickers), dtype=np.float32))
    forward_return = metrics.get("forward_return", np.zeros(len(tickers), dtype=np.float32))
    is_long = metrics.get("is_long", np.zeros(len(tickers), dtype=bool)).astype(bool)
    is_short = metrics.get("is_short", np.zeros(len(tickers), dtype=bool)).astype(bool)

    valid_clusters = sorted(int(c) for c in np.unique(cluster_id) if int(c) >= 0)

    for cid in valid_clusters:
        mask = cluster_id == cid
        idx = np.where(mask)[0]

        if len(idx) == 0:
            continue

        # Top tickers by stress are usually more informative than arbitrary order.
        top_stress_idx = idx[np.argsort(stress[idx])[::-1]][:max_names]
        top_longs_idx = idx[is_long[idx]]
        top_shorts_idx = idx[is_short[idx]]

        if len(top_longs_idx):
            top_longs_idx = top_longs_idx[np.argsort(conf[top_longs_idx])[::-1]][:max_names]
        if len(top_shorts_idx):
            top_shorts_idx = top_shorts_idx[np.argsort(conf[top_shorts_idx])[::-1]][:max_names]

        rows.append({
            "frame": frame_id,
            "date": str(snap_date.date()),
            "return_date": str(ret_date.date()),
            "cluster_id": cid,
            "node_count": int(len(idx)),
            "long_count": int(is_long[idx].sum()),
            "short_count": int(is_short[idx].sum()),
            "top_tickers_by_stress": "|".join(tickers_arr[top_stress_idx].astype(str).tolist()),
            "top_longs": "|".join(tickers_arr[top_longs_idx].astype(str).tolist()) if len(top_longs_idx) else "",
            "top_shorts": "|".join(tickers_arr[top_shorts_idx].astype(str).tolist()) if len(top_shorts_idx) else "",
            "stress_mean": float(np.nanmean(stress[idx])),
            "stress_p95": float(np.nanpercentile(stress[idx], 95)),
            "entropy_z_mean": float(np.nanmean(entropy_z[idx])),
            "realized_vol_z_mean": float(np.nanmean(realized_vol_z[idx])),
            "forward_return_mean": float(np.nanmean(forward_return[idx])),
        })

    return rows



def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    frames_dir = out_dir / "frames"

    if args.force_rebuild and out_dir.exists():
        shutil.rmtree(out_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    print("=== build_market_graph_frames.py ===")
    print(f"  CuPy available: {HAS_CUPY}")
    print(f"  use CuPy:       {args.use_cupy and HAS_CUPY}")
    print(f"  max_nodes:      {args.max_nodes}")
    print(f"  top_k_edges:    {args.top_k_edges}")
    print(f"  max_edges:      {args.max_edges}")
    print(f"  layout_engine:  {args.layout_engine}")
    print(f"  scipy eigsh:    {HAS_SCIPY_EIGSH}")
    print(f"  sklearn kmeans: {HAS_SKLEARN_CLUSTER}")

    returns_meta = Path(args.returns_meta)
    returns, meta = load_returns(returns_meta)
    all_dates = pd.to_datetime(meta["dates"])
    all_tickers = [normalize_ticker(t) for t in meta["tickers"]]
    ticker_to_idx = {t: i for i, t in enumerate(all_tickers)}

    signals = load_signals(Path(args.signals))
    context = load_context(args.context)
    requested_dates = generate_requested_dates(args.start_date, args.end_date, args.frame_step_days)
    rng = np.random.default_rng(args.seed)

    prev_coords: np.ndarray | None = None
    prev_tickers: list[str] | None = None
    prev_corr: np.ndarray | None = None

    frames: list[dict] = []
    frame_summaries: list[dict] = []
    cluster_summaries: list[dict] = []
    all_x: list[float] = []
    all_y: list[float] = []
    all_z: list[float] = []
    all_color: list[float] = []
    all_corr_delta: list[float] = []

    t0 = time.time()
    frame_id = 0
    seen_snap_dates: set[pd.Timestamp] = set()
    print(f"\nDate range: {args.start_date} → {args.end_date} ({len(requested_dates)} candidate frames)")

    for requested_date in requested_dates:
        snap_date = nearest_prior_date(signals["date"], requested_date)
        if snap_date is None:
            print(f"  [skip] {requested_date.date()} no prior signal date")
            continue

        if snap_date in seen_snap_dates:
            print(f"  [skip] {requested_date.date()} duplicate snap_date {snap_date.date()}")
            continue
        seen_snap_dates.add(snap_date)

        ret_date = nearest_prior_date(pd.Series(all_dates), snap_date)
        if ret_date is None:
            print(f"  [skip] {snap_date.date()} no prior return date")
            continue
        date_idx_arr = np.where(all_dates == ret_date)[0]
        if len(date_idx_arr) == 0:
            print(f"  [skip] {snap_date.date()} return date missing")
            continue
        date_idx = int(date_idx_arr[0])
        if date_idx + 1 < args.lookback:
            print(f"  [skip] {snap_date.date()} insufficient lookback")
            continue

        sig_on_date = signals[signals["date"] == snap_date].copy()
        if sig_on_date.empty:
            print(f"  [skip] {snap_date.date()} no signals")
            continue

        tickers = select_nodes(
            signals_on_date=sig_on_date,
            ticker_to_idx=ticker_to_idx,
            returns=returns,
            date_idx=date_idx,
            lookback=args.lookback,
            max_nodes=args.max_nodes,
            top_signal_nodes=args.top_signal_nodes,
            extra_signal_neighborhood=args.extra_signal_neighborhood,
            extra_random_nodes=args.extra_random_nodes,
            extra_volatile_nodes=args.extra_volatile_nodes,
            rng=rng,
        )
        if len(tickers) < 10:
            print(f"  [skip] {snap_date.date()} too few nodes: {len(tickers)}")
            continue

        node_idx = np.array([ticker_to_idx[t] for t in tickers], dtype=np.int32)
        start_idx = max(0, date_idx - args.lookback + 1)
        window = returns[start_idx : date_idx + 1, :][:, node_idx]
        finite_rate = np.isfinite(window).mean(axis=0)
        keep = finite_rate >= 0.80

        tickers = [t for t, k in zip(tickers, keep) if k]
        node_idx = node_idx[keep]
        window = window[:, keep]
        finite_rate = finite_rate[keep]
        if len(tickers) < 10:
            print(f"  [skip] {snap_date.date()} too few valid nodes")
            continue

        corr = corrcoef_fast(window, use_cupy=args.use_cupy)

        cluster_id = np.full(len(tickers), -1, dtype=np.int32)

        if args.layout_engine == "mds":
            coords = classical_mds(corr)
        elif args.layout_engine == "cluster-ring":
            coords, cluster_id = cluster_ring_layout(
                corr,
                cluster_count=args.cluster_count,
                anchor_strength=args.cluster_anchor_strength,
            )
        else:
            coords = corr_pca_fast_layout(corr)

        # Align layout only when the node universe is identical.
        # Do NOT update prev_tickers here, because edge tension still needs
        # the previous frame's ticker map.
        if prev_tickers == tickers:
            coords = procrustes_align(coords, prev_coords)

        metrics = build_node_metrics(
            tickers=tickers,
            ticker_to_idx=ticker_to_idx,
            returns=returns,
            date_idx=date_idx,
            window=window,
            signals_on_date=sig_on_date,
            forward_days=args.forward_days,
            corr=corr,
            z_mode=args.z_mode,
            color_mode=args.color_mode,
        )

        edge_src, edge_dst, edge_corr = topk_edges(corr, args.top_k_edges, args.min_edge_corr, args.max_edges)

        # Edge tension / correlation delta across frames.
        #
        # The node list can change from frame to frame, so do NOT require the
        # whole node universe to be identical. Instead, compare each current
        # visible edge against the previous frame if both endpoint tickers
        # existed in the previous frame.
        #
        # Positive delta = the fabric stitching tightened.
        # Negative delta = the fabric stitching loosened.
        edge_corr_delta = np.zeros_like(edge_corr, dtype=np.float32)

        if prev_corr is not None and prev_tickers is not None and len(edge_src):
            prev_pos = {t: i for i, t in enumerate(prev_tickers)}

            for k, (a, b) in enumerate(zip(edge_src, edge_dst)):
                ta = tickers[int(a)]
                tb = tickers[int(b)]

                ia = prev_pos.get(ta)
                ib = prev_pos.get(tb)

                if ia is None or ib is None:
                    continue

                old_corr = float(prev_corr[ia, ib])
                new_corr = float(corr[int(a), int(b)])

                if np.isfinite(old_corr) and np.isfinite(new_corr):
                    edge_corr_delta[k] = new_corr - old_corr

        prev_corr = corr.copy()
        prev_coords = coords.copy()
        prev_tickers = list(tickers)

        ctx = {}
        if context is not None and "date" in context.columns:
            ctx_date = nearest_prior_date(context["date"], snap_date)
            if ctx_date is not None:
                row = context[context["date"] == ctx_date].tail(1)
                if not row.empty:
                    for col in row.columns:
                        if col == "date":
                            continue
                        val = row.iloc[0][col]
                        if isinstance(val, (np.floating, np.integer, float, int)):
                            ctx[col] = float(val)
                        elif pd.notna(val):
                            ctx[col] = str(val)

        path = frames_dir / f"frame_{frame_id:04d}.npz"
        np.savez_compressed(
            path,
            date=np.array(str(snap_date.date())),
            return_date=np.array(str(ret_date.date())),
            tickers=np.array(tickers, dtype=object),
            node_idx=node_idx.astype(np.int32),
            cluster_id=cluster_id.astype(np.int32),
            x=coords[:, 0].astype(np.float32),
            y=coords[:, 1].astype(np.float32),
            z=metrics["z"].astype(np.float32),
            color=metrics["color"].astype(np.float32),
            forward_return=metrics["forward_return"].astype(np.float32),
            realized_vol=metrics["realized_vol"].astype(np.float32),
            realized_vol_z=metrics["realized_vol_z"].astype(np.float32),
            entropy_proxy=metrics["entropy_proxy"].astype(np.float32),
            entropy_z=metrics["entropy_z"].astype(np.float32),
            corr_degree=metrics["corr_degree"].astype(np.float32),
            stress=metrics["stress"].astype(np.float32),
            peer_spread_z=metrics["peer_spread_z"].astype(np.float32),
            confidence=metrics["confidence"].astype(np.float32),
            finite_rate=finite_rate.astype(np.float32),
            is_long=metrics["is_long"].astype(bool),
            is_short=metrics["is_short"].astype(bool),
            edge_src=edge_src,
            edge_dst=edge_dst,
            edge_corr=edge_corr,
            edge_corr_delta=edge_corr_delta,
            ctx_json=np.array(json.dumps(ctx)),
        )

        frames.append({
            "frame": frame_id,
            "date": str(snap_date.date()),
            "return_date": str(ret_date.date()),
            "path": str(path),
            "nodes": len(tickers),
            "edges": int(len(edge_src)),
            "long": int(metrics["is_long"].sum()),
            "short": int(metrics["is_short"].sum()),
        })

        frame_summaries.append({
            "frame": frame_id,
            "date": str(snap_date.date()),
            "return_date": str(ret_date.date()),
            "nodes": len(tickers),
            "edges": int(len(edge_src)),
            "long": int(metrics["is_long"].sum()),
            "short": int(metrics["is_short"].sum()),
            "avg_edge_corr": float(np.nanmean(edge_corr)) if len(edge_corr) else 0.0,
            "avg_abs_edge_corr_delta": float(np.nanmean(np.abs(edge_corr_delta))) if len(edge_corr_delta) else 0.0,
            "avg_edge_corr_delta": float(np.nanmean(edge_corr_delta)) if len(edge_corr_delta) else 0.0,
            "stress_mean": float(np.nanmean(metrics.get("stress", np.array([0.0])))),
            "stress_p95": float(np.nanpercentile(metrics.get("stress", np.array([0.0])), 95)),
            "entropy_z_mean": float(np.nanmean(metrics.get("entropy_z", np.array([0.0])))),
            "realized_vol_z_mean": float(np.nanmean(metrics.get("realized_vol_z", np.array([0.0])))),
        })

        cluster_summaries.extend(
            summarize_clusters(
                frame_id=frame_id,
                snap_date=snap_date,
                ret_date=ret_date,
                tickers=tickers,
                cluster_id=cluster_id,
                metrics=metrics,
            )
        )

        all_x.extend(coords[:, 0].astype(float).tolist())
        all_y.extend(coords[:, 1].astype(float).tolist())
        all_z.extend(metrics["z"][np.isfinite(metrics["z"])].astype(float).tolist())
        all_color.extend(metrics["color"][np.isfinite(metrics["color"])].astype(float).tolist())
        all_corr_delta.extend(edge_corr_delta[np.isfinite(edge_corr_delta)].astype(float).tolist())

        print(f"  [{frame_id:03d}] {snap_date.date()} nodes={len(tickers):4d} edges={len(edge_src):5d} long={int(metrics['is_long'].sum())} short={int(metrics['is_short'].sum())}")
        frame_id += 1

    if not frames:
        raise RuntimeError("No graph frames built.")

    x_min, x_max = pct_limits(all_x, 0, 100)
    y_min, y_max = pct_limits(all_y, 0, 100)
    z_min, z_max = pct_limits(all_z, 1, 99)
    c_min, c_max = pct_limits(all_color, 1, 99)
    d_min, d_max = pct_limits(all_corr_delta, 1, 99)

    manifest = {
        "kind": "market_graph_fabric_frames",
        "frames": frames,
        "parameters": vars(args),
        "returns_meta": str(returns_meta),
        "signals": str(Path(args.signals)),
        "context": args.context,
        "global_limits": {
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "z_min": z_min,
            "z_max": z_max,
            "color_min": c_min,
            "color_max": c_max,
            "corr_delta_min": d_min,
            "corr_delta_max": d_max,
        },
        "description": {
            "nodes": "Stocks are fabric vertices.",
            "edges": "Top-k rolling correlations are stitching/springs.",
            "x_y": "Rolling correlation geometry via classical MDS.",
            "z": args.z_mode,
            "color": args.color_mode,
            "edge_corr_delta": "Change in correlation for visible edges when comparable.",
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    pd.DataFrame(frame_summaries).to_csv(out_dir / "frame_summary.csv", index=False)
    pd.DataFrame(cluster_summaries).to_csv(out_dir / "cluster_summary.csv", index=False)

    print(f"\nDone in {time.time() - t0:.1f}s")
    print(f"✓ manifest: {out_dir / 'manifest.json'}")
    print(f"✓ summary:  {out_dir / 'frame_summary.csv'}")
    print(f"✓ clusters: {out_dir / 'cluster_summary.csv'}")
    print(f"✓ frames:   {frames_dir}")
    print(f"✓ built:    {len(frames)} frames")
    print(f"  x_lim:    [{x_min:.4f}, {x_max:.4f}]")
    print(f"  y_lim:    [{y_min:.4f}, {y_max:.4f}]")
    print(f"  z_lim:    [{z_min:.4f}, {z_max:.4f}]")
    print(f"  color:    [{c_min:.4f}, {c_max:.4f}]")
    print()
    print("Next visualizer target:")
    print("  python visuals/visualize_market_graph_fabric.py \\")
    print(f"    --frames-dir {out_dir} --safe-mode")


if __name__ == "__main__":
    main()
