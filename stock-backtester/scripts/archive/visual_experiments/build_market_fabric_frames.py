"""
build_market_fabric_frames.py
==============================
Offline heavy computation for the Market Fabric Visualizer.

This script runs once per date range and caches everything to disk.
The interactive visualizer (visualize_market_fabric_vispy.py) reads
those frames at runtime — no correlation math, no MDS, no interpolation
in the animation loop.

WHY PRECOMPUTING MATTERS
-------------------------
Rolling correlation for 300 tickers × 126 days costs ~10ms per frame on CPU.
MDS eigendecomposition: ~5ms.
RBF interpolation to 160×160 grid: ~80ms.
Gaussian filter: ~2ms.
Total per-frame: ~100ms × 25 frames = 2.5 seconds for a typical animation.
That's acceptable offline, but would make interactive playback at 30fps impossible.
Precomputing these once and storing the grid arrays means the visualizer only
moves float32 arrays from RAM → GPU buffer, which takes < 1ms per frame.

WHY FIXED TOPOLOGY MATTERS
---------------------------
If the number of grid cells changes between frames, the GPU mesh buffer must be
reallocated (glBufferData instead of glBufferSubData). Reallocation can stall the
GPU pipeline and causes frame drops. By fixing the grid resolution once and using
the same NxN grid for every frame (masking empty cells via alpha=0 rather than
removing them), we can always use glBufferSubData — fast path.

CORRELATION FABRIC EXPLAINED
------------------------------
Stock returns in the lookback window define a correlation matrix.
Mantegna distance d(i,j) = sqrt(0.5*(1-corr(i,j))) puts it in metric space.
Classical MDS then finds 2D Euclidean coordinates that best preserve those distances.
Highly correlated stocks land close together; uncorrelated stocks land far apart.
The x/y plane IS the rolling correlation geometry — it changes every frame.

Z-MODE / COLOR-MODE
--------------------
z-mode  : controls surface height (what makes valleys / spikes)
  peer_spread_z  — long signals sink (valleys), short signals rise (spikes)
  forward_return — realized gain/loss over next N days
  volatility     — annualized realized vol → instability terrain
  confidence     — adjusted_confidence from signal file → conviction terrain

color-mode : independent heatmap on same surface (can differ from z-mode)
  Typical combo: z=peer_spread_z + color=forward_return → signal shape
  heated by whether the thesis worked.

VALLEYS / SPIKES
-----------------
When z-mode=peer_spread_z:
  Long signal tickers have negative peer_spread_z → they sink → VALLEYS.
  Short signal tickers have positive peer_spread_z → they rise → SPIKES.
  The visualization lets you see whether those valleys/spikes later
  become profitable (green heat) or not (red heat).

PROCRUSTES ALIGNMENT
---------------------
MDS is defined up to rotation/reflection/translation.
Without Procrustes, each frame's fabric would spin to a random orientation,
making animation look like static. Procrustes finds the best rotation R
that maps the new frame's shared tickers onto the previous frame's positions,
so the fabric appears to smoothly deform rather than jump.

GPU / RUST HOOKS (marked with # PERF: comments)
-------------------------------------------------
Current CPU bottleneck:
  - corrcoef: O(T * N^2)  → CuPy or Rust/rayon candidate
  - eigh:     O(N^3)      → CuPy candidate
  - RBF:      O(N^3)      → sparse GPU approximation candidate
  - gaussian_filter: trivial

QUALITY PRESETS
---------------
--quality low     grid=80,  max_nodes=120   ~1MB/frame
--quality medium  grid=120, max_nodes=200   ~2MB/frame
--quality high    grid=180, max_nodes=350   ~4MB/frame  (default)
--quality ultra   grid=240, max_nodes=500   ~7MB/frame  (warns)

OUTPUTS
-------
<out-dir>/
  manifest.json             — global limits, dates, parameters
  frames/
    frame_0000.npz          — per-frame arrays
    frame_0001.npz
    ...

EXAMPLE
-------
python scripts/build_market_fabric_frames.py \\
  --returns-meta /tmp/quant_returns/.../returns_meta.json \\
  --signals outputs/signals/large_universe_peer_spread_long_top5_v1.parquet \\
  --context outputs/context/market_context.parquet \\
  --out-dir outputs/reports/plots/market_fabric_vispy_2020 \\
  --start-date 2020-02-01 --end-date 2020-06-30 \\
  --frame-step-days 5 --lookback 126 --forward-days 60 \\
  --top-signals 8 --max-nodes 400 \\
  --extra-node-mode mixed --extra-nodes 250 \\
  --grid-size 160 --smooth-sigma 2.0 \\
  --z-mode peer_spread_z --color-mode forward_return
"""

from __future__ import annotations

import argparse
import json
import time
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ── Optional GPU ──────────────────────────────────────────────────────────────
try:
    import cupy as cp

    _CUPY = True
except ImportError:
    cp = None
    _CUPY = False

# ── Scipy (required for good interpolation) ───────────────────────────────────
try:
    from scipy.spatial import cKDTree
    from scipy.interpolate import RBFInterpolator, griddata
    from scipy.ndimage import gaussian_filter

    _SCIPY = True
    _RBF = True
except Exception:
    try:
        from scipy.spatial import cKDTree
        from scipy.interpolate import griddata
        from scipy.ndimage import gaussian_filter

        _SCIPY = True
        _RBF = False
        RBFInterpolator = None
    except Exception:
        _SCIPY = False
        _RBF = False
        cKDTree = griddata = gaussian_filter = RBFInterpolator = None  # type: ignore


# ═════════════════════════════════════════════════════════════════════════════
# QUALITY PRESETS
# ═════════════════════════════════════════════════════════════════════════════

QUALITY_PRESETS = {
    "low": dict(grid_size=80, max_nodes=120, smooth_sigma=1.2),
    "medium": dict(grid_size=120, max_nodes=200, smooth_sigma=1.5),
    "high": dict(grid_size=180, max_nodes=350, smooth_sigma=2.0),
    "ultra": dict(grid_size=240, max_nodes=500, smooth_sigma=2.5),
}

# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--returns-meta", required=True)
    p.add_argument("--signals", required=True, help="Long signal parquet")
    p.add_argument(
        "--short-signals", default=None, help="Short signal parquet (optional)"
    )
    p.add_argument("--context", default=None, help="Market context parquet (optional)")
    p.add_argument("--out-dir", required=True)

    # Date range
    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    p.add_argument("--frame-step-days", type=int, default=5)

    # Nodes
    p.add_argument("--lookback", type=int, default=126)
    p.add_argument("--forward-days", type=int, default=60)
    p.add_argument("--top-signals", type=int, default=8)
    p.add_argument(
        "--extra-node-mode",
        choices=["none", "volatile", "movers", "mixed"],
        default="mixed",
    )
    p.add_argument("--extra-nodes", type=int, default=250)

    # Quality preset (overrides grid-size / max-nodes / smooth-sigma)
    p.add_argument(
        "--quality",
        choices=["low", "medium", "high", "ultra"],
        default=None,
        help="Quality preset; overrides --grid-size/--max-nodes/--smooth-sigma",
    )
    p.add_argument("--max-nodes", type=int, default=350)
    p.add_argument("--grid-size", type=int, default=180)
    p.add_argument("--smooth-sigma", type=float, default=2.0)

    # Modes
    p.add_argument(
        "--z-mode",
        choices=["peer_spread_z", "forward_return", "volatility", "confidence"],
        default="peer_spread_z",
    )
    p.add_argument(
        "--color-mode",
        choices=["peer_spread_z", "forward_return", "volatility", "confidence"],
        default="forward_return",
    )
    p.add_argument(
        "--interpolation-method",
        choices=["rbf", "linear", "cubic", "nearest"],
        default="rbf",
    )
    p.add_argument("--winsorize-z", type=float, default=0.02)
    p.add_argument("--winsorize-color", type=float, default=0.02)
    p.add_argument("--z-scale", type=float, default=1.0)

    # Cache
    p.add_argument("--no-cache", action="store_true")
    p.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Delete and rebuild all cached frames",
    )

    return p.parse_args()


# ═════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═════════════════════════════════════════════════════════════════════════════


def load_returns(meta_path: Path) -> tuple[np.ndarray, dict]:
    meta = json.loads(meta_path.read_text())
    dtype = np.float32 if meta["dtype"] == "float32" else np.float64
    arr = np.fromfile(meta_path.parent / meta["binary_file"], dtype=dtype)
    arr = arr.reshape(int(meta["rows"]), int(meta["cols"])).astype(
        np.float32, copy=False
    )
    return arr, meta


def nearest_prior(series: pd.Series, ts: pd.Timestamp) -> pd.Timestamp:
    eligible = series[series <= ts]
    if eligible.empty:
        raise ValueError(f"No dates on or before {ts.date()}")
    return eligible.max()


# ═════════════════════════════════════════════════════════════════════════════
# CORRELATION + MDS
# ═════════════════════════════════════════════════════════════════════════════


def corrcoef_fast(window: np.ndarray) -> np.ndarray:
    # PERF: replace with CuPy or Rust/rayon for large windows
    if _CUPY:
        try:
            w = cp.asarray(window, dtype=cp.float32)
            w = w - w.mean(axis=0, keepdims=True)
            n = cp.linalg.norm(w, axis=0, keepdims=True).clip(1e-12)
            wn = w / n
            return cp.asnumpy(wn.T @ wn)
        except Exception as e:
            warnings.warn(f"CuPy corrcoef failed ({e}); using NumPy")
    return np.corrcoef(window, rowvar=False)


def classical_mds(corr: np.ndarray) -> np.ndarray:
    # PERF: eigh is O(N^3); CuPy eigh or LAPACK dsyevd via Rust for N>300
    corr = np.nan_to_num(np.clip(corr, -0.9999, 0.9999))
    d2 = 0.5 * (1.0 - corr)
    n = d2.shape[0]
    H = np.eye(n) - np.ones((n, n)) / n
    G = -0.5 * (H @ d2 @ H)
    if _CUPY:
        try:
            v, e = cp.linalg.eigh(cp.asarray(G.astype(np.float64)))
            vals, vecs = cp.asnumpy(v), cp.asnumpy(e)
        except Exception:
            vals, vecs = np.linalg.eigh(G)
    else:
        vals, vecs = np.linalg.eigh(G)
    order = np.argsort(vals)[::-1]
    vals = np.maximum(vals[order][:2], 0.0)
    vecs = vecs[:, order][:, :2]
    return (vecs * np.sqrt(vals + 1e-12)).astype(np.float32)


def procrustes_align(
    ref_xy: np.ndarray, new_xy: np.ndarray, ref_nodes: list[str], new_nodes: list[str]
) -> np.ndarray:
    """Rotate/reflect new_xy onto ref_xy using shared ticker anchors."""
    shared = list(set(ref_nodes) & set(new_nodes))
    if len(shared) < 3:
        return new_xy
    ri = [ref_nodes.index(t) for t in shared]
    ni = [new_nodes.index(t) for t in shared]
    A = ref_xy[ri] - ref_xy[ri].mean(0)
    B = new_xy[ni] - new_xy[ni].mean(0)
    U, _, Vt = np.linalg.svd(A.T @ B)
    R = (U @ Vt).T
    c_b, c_a = new_xy[ni].mean(0), ref_xy[ri].mean(0)
    return ((new_xy - c_b) @ R + c_a).astype(np.float32)


# ═════════════════════════════════════════════════════════════════════════════
# NODE SELECTION
# ═════════════════════════════════════════════════════════════════════════════


def build_nodes(
    sig_df: pd.DataFrame,
    short_df: Optional[pd.DataFrame],
    top_signals: int,
    max_nodes: int,
    ticker_to_idx: dict,
    extra_mode: str,
    extra_budget: int,
    returns: np.ndarray,
    all_tickers: list[str],
    date_idx: int,
    lookback: int,
    forward_days: int,
) -> tuple[list[str], set[str], set[str]]:
    long_top = (
        sig_df.sort_values("adjusted_confidence", ascending=False)
        .drop_duplicates("ticker")
        .head(top_signals)
    )
    long_set = set(long_top["ticker"].astype(str).str.upper())

    short_top = pd.DataFrame()
    short_set: set[str] = set()
    if short_df is not None and len(short_df) > 0:
        short_top = (
            short_df.sort_values("adjusted_confidence", ascending=False)
            .drop_duplicates("ticker")
            .head(top_signals)
        )
        short_set = set(short_top["ticker"].astype(str).str.upper())

    seen: set[str] = set()
    nodes: list[str] = []

    def add(t: str) -> bool:
        t = str(t).upper().strip()
        if t and t not in seen and t in ticker_to_idx and len(nodes) < max_nodes:
            seen.add(t)
            nodes.append(t)
            return True
        return False

    for _, row in long_top.iterrows():
        add(row["ticker"])
        for p in str(row.get("peer_list", "")).split("|"):
            add(p)
    for _, row in short_top.iterrows():
        add(row["ticker"])
        for p in str(row.get("peer_list", "")).split("|"):
            add(p)

    # Extra nodes to densify the surface
    if extra_mode != "none" and len(nodes) < max_nodes and extra_budget > 0:
        start_idx = max(0, date_idx - lookback + 1)
        cands = [t for t in all_tickers if t not in seen]
        rng = np.random.default_rng(42)
        if len(cands) > 1500:
            cands = rng.choice(cands, 1500, replace=False).tolist()
        cidx = [ticker_to_idx[t] for t in cands]
        w = returns[start_idx : date_idx + 1, :][:, cidx]
        fr = np.isfinite(w).mean(0)
        ok = [(t, i) for t, i, f in zip(cands, cidx, fr) if f >= 0.75]
        if ok:
            ok_t, ok_i = zip(*ok)
            ok_t, ok_i = list(ok_t), list(ok_i)
            w_ok = returns[start_idx : date_idx + 1, :][:, ok_i]
            scores_v = np.nanstd(w_ok, axis=0)
            if extra_mode in ("movers", "mixed"):
                fe = min(returns.shape[0], date_idx + forward_days + 1)
                fut = returns[date_idx + 1 : fe, :][:, ok_i]
                scores_m = np.abs(np.nansum(fut, axis=0))
            else:
                scores_m = scores_v.copy()
            if extra_mode == "volatile":
                sc = scores_v
            elif extra_mode == "movers":
                sc = scores_m
            else:
                sc = 0.5 * scores_v / (scores_v.max() + 1e-9) + 0.5 * scores_m / (
                    scores_m.max() + 1e-9
                )
            added = 0
            for i in np.argsort(sc)[::-1]:
                if added >= extra_budget:
                    break
                if add(ok_t[i]):
                    added += 1

    return nodes[:max_nodes], long_set, short_set


# ═════════════════════════════════════════════════════════════════════════════
# VALUE COMPUTATION
# ═════════════════════════════════════════════════════════════════════════════


def compute_values(
    mode: str,
    nodes: list[str],
    sig_map: Optional[pd.DataFrame],
    short_map: Optional[pd.DataFrame],
    returns: np.ndarray,
    node_indices: list[int],
    date_idx: int,
    forward_days: int,
    lookback: int,
) -> np.ndarray:
    n = len(nodes)
    v = np.zeros(n, np.float32)

    if mode == "peer_spread_z":
        for i, t in enumerate(nodes):
            if sig_map is not None and t in sig_map.index:
                v[i] = float(sig_map.loc[t, "peer_spread_z"])
            elif short_map is not None and t in short_map.index:
                v[i] = float(short_map.loc[t, "peer_spread_z"])
    elif mode == "forward_return":
        fe = min(returns.shape[0], date_idx + forward_days + 1)
        v = np.nansum(returns[date_idx + 1 : fe, :][:, node_indices], axis=0).astype(
            np.float32
        )
    elif mode == "volatility":
        si = max(0, date_idx - lookback + 1)
        v = (
            np.nanstd(returns[si : date_idx + 1, :][:, node_indices], axis=0)
            * np.sqrt(252)
        ).astype(np.float32)
    elif mode == "confidence":
        for i, t in enumerate(nodes):
            if sig_map is not None and t in sig_map.index:
                v[i] = float(sig_map.loc[t, "adjusted_confidence"])
            elif short_map is not None and t in short_map.index:
                v[i] = float(short_map.loc[t, "adjusted_confidence"])
    return v


def winsorize(arr: np.ndarray, frac: float) -> np.ndarray:
    if frac <= 0:
        return arr
    lo, hi = np.nanpercentile(arr, frac * 100), np.nanpercentile(arr, (1 - frac) * 100)
    return np.clip(arr, lo, hi)


# ═════════════════════════════════════════════════════════════════════════════
# GRID INTERPOLATION (heavy — runs offline only)
# ═════════════════════════════════════════════════════════════════════════════


def interpolate_grid(
    x: np.ndarray,
    y: np.ndarray,
    values: np.ndarray,
    grid_size: int,
    method: str,
    smooth_sigma: float,
    mask_factor: float = 3.5,
    mask_pct: float = 85.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Scatter (x,y,values) → dense grid_size×grid_size regular grid.
    Mask cells farther than mask_factor × typical anchor spacing.
    Smooth with gaussian_filter.
    # PERF: RBF solve is O(N^3). For N>400 consider sparse GP or move to GPU.
    """
    pad = 0.08
    xr = x.max() - x.min() + 1e-8
    yr = y.max() - y.min() + 1e-8
    xl, xh = x.min() - pad * xr, x.max() + pad * xr
    yl, yh = y.min() - pad * yr, y.max() + pad * yr

    gx = np.linspace(xl, xh, grid_size, dtype=np.float32)
    gy = np.linspace(yl, yh, grid_size, dtype=np.float32)
    GX, GY = np.meshgrid(gx, gy)
    gpts = np.stack([GX.ravel(), GY.ravel()], 1)
    pts = np.stack([x, y], 1).astype(np.float64)
    vals = values.astype(np.float64)

    gz_flat: Optional[np.ndarray] = None

    # ── RBF (preferred) ────────────────────────────────────────────────────
    if _RBF and method == "rbf" and RBFInterpolator is not None:
        try:
            rbf = RBFInterpolator(pts, vals, kernel="thin_plate_spline", smoothing=0.5)
            gz_flat = rbf(gpts.astype(np.float64)).astype(np.float32)
        except Exception as e:
            warnings.warn(f"RBF failed ({e}); trying griddata cubic")

    # ── griddata fallback ──────────────────────────────────────────────────
    if gz_flat is None and _SCIPY:
        gd_m = method if method != "rbf" else "cubic"
        try:
            gz_flat = griddata(pts, vals, gpts, method=gd_m, fill_value=np.nan).astype(
                np.float32
            )
            nan_m = ~np.isfinite(gz_flat)
            if nan_m.any():
                gz_flat[nan_m] = griddata(
                    pts, vals, gpts[nan_m], method="nearest"
                ).astype(np.float32)
        except Exception as e:
            warnings.warn(f"griddata failed ({e})")

    # ── Nearest-neighbor last resort ───────────────────────────────────────
    if gz_flat is None:
        if _SCIPY:
            gz_flat = griddata(pts, vals, gpts, method="nearest").astype(np.float32)
        else:
            gz_flat = np.zeros(grid_size * grid_size, np.float32)

    GZ = gz_flat.reshape(grid_size, grid_size)

    # ── Gaussian smoothing ─────────────────────────────────────────────────
    if smooth_sigma > 0 and gaussian_filter is not None:
        nm = ~np.isfinite(GZ)
        tmp = np.where(np.isfinite(GZ), GZ, 0.0)
        GZ = gaussian_filter(tmp.astype(np.float64), sigma=smooth_sigma).astype(
            np.float32
        )
        GZ[nm] = np.nan

    # ── Distance mask ──────────────────────────────────────────────────────
    if _SCIPY and cKDTree is not None:
        tree = cKDTree(pts)
        dists, _ = tree.query(gpts, k=1)
        if len(pts) > 1:
            nn, _ = tree.query(pts, k=min(2, len(pts)))
            spacing = nn[:, -1] if nn.ndim == 2 else nn
            spacing = spacing[spacing > 0]
            thr = (
                np.percentile(spacing, mask_pct) * mask_factor
                if len(spacing)
                else np.inf
            )
        else:
            thr = np.inf
        far = dists.reshape(grid_size, grid_size) > thr
        GZ[far] = np.nan

    return GX, GY, GZ


# ═════════════════════════════════════════════════════════════════════════════
# FIXED GRID COORDINATES (shared across all frames)
# ═════════════════════════════════════════════════════════════════════════════


def build_fixed_grid_vertices(
    grid_size: int,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build the fixed (grid_size*grid_size, 3) vertex array and face index array.
    XY coords are fixed forever; only Z changes per frame.
    This is the key to stable mesh topology — we never change faces.
    """
    gx = np.linspace(x_range[0], x_range[1], grid_size, dtype=np.float32)
    gy = np.linspace(y_range[0], y_range[1], grid_size, dtype=np.float32)
    GX, GY = np.meshgrid(gx, gy)

    # Vertices: (N*N, 3) — Z is placeholder, filled per frame
    verts = np.zeros((grid_size * grid_size, 3), dtype=np.float32)
    verts[:, 0] = GX.ravel()
    verts[:, 1] = GY.ravel()
    # verts[:, 2] = 0  (filled per frame)

    # Faces: 2 triangles per cell
    rows, cols = grid_size, grid_size
    faces = []
    for i in range(rows - 1):
        for j in range(cols - 1):
            k = i * cols + j
            faces.append([k, k + 1, k + cols])
            faces.append([k + 1, k + cols + 1, k + cols])
    faces_arr = np.array(faces, dtype=np.uint32)

    return GX, GY, verts, faces_arr


# ═════════════════════════════════════════════════════════════════════════════
# MAIN BUILD LOOP
# ═════════════════════════════════════════════════════════════════════════════


def main() -> None:
    args = parse_args()

    # Apply quality preset
    if args.quality:
        preset = QUALITY_PRESETS[args.quality]
        if args.quality == "ultra":
            print(
                f"⚠  WARNING: --quality ultra uses large grids. "
                f"May be slow on CPU. Consider using a machine with CuPy."
            )
        args.grid_size = preset["grid_size"]
        args.max_nodes = preset["max_nodes"]
        args.smooth_sigma = preset["smooth_sigma"]

    print("=== build_market_fabric_frames.py ===")
    print(f"  CuPy:        {'✓' if _CUPY else '✗ (NumPy CPU fallback)'}")
    print(f"  Scipy:       {'✓' if _SCIPY else '✗ (reduced quality)'}")
    print(f"  Scipy RBF:   {'✓' if _RBF else '✗ (griddata fallback)'}")
    print(f"  grid_size:   {args.grid_size}² = {args.grid_size**2:,} cells")
    print(f"  max_nodes:   {args.max_nodes}")
    mem_mb = args.grid_size**2 * 4 * 4 / 1e6  # 4 float32 arrays per frame
    print(f"  ~mem/frame:  {mem_mb:.1f} MB")
    print()

    # ── Dirs ──────────────────────────────────────────────────────────────
    out_dir = Path(args.out_dir)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    if args.force_rebuild:
        for f in frames_dir.glob("frame_*.npz"):
            f.unlink()
        print("  Cleared cached frames.")

    # ── Load returns ───────────────────────────────────────────────────────
    print(f"Loading returns: {args.returns_meta}")
    returns, meta = load_returns(Path(args.returns_meta))
    all_dates = pd.to_datetime(meta["dates"])
    all_tickers = [str(t).upper() for t in meta["tickers"]]
    t2i = {t: i for i, t in enumerate(all_tickers)}
    print(f"  {returns.shape[0]} dates × {returns.shape[1]} tickers")

    # ── Load signals ───────────────────────────────────────────────────────
    print(f"Loading signals: {args.signals}")
    sigs = pd.read_parquet(args.signals)
    sigs["date"] = pd.to_datetime(sigs["date"])
    sigs["ticker"] = sigs["ticker"].astype(str).str.upper()

    short_sigs = None
    if args.short_signals:
        short_sigs = pd.read_parquet(args.short_signals)
        short_sigs["date"] = pd.to_datetime(short_sigs["date"])
        short_sigs["ticker"] = short_sigs["ticker"].astype(str).str.upper()

    # ── Load context (optional) ────────────────────────────────────────────
    context_df = None
    if args.context:
        try:
            context_df = pd.read_parquet(args.context)
            context_df["date"] = pd.to_datetime(context_df["date"])
        except Exception as e:
            warnings.warn(f"Context load failed: {e}")

    # ── Date list ──────────────────────────────────────────────────────────
    render_dates = list(
        pd.date_range(args.start_date, args.end_date, freq=f"{args.frame_step_days}D")
    )
    print(
        f"\nDate range: {args.start_date} → {args.end_date}  "
        f"({len(render_dates)} candidate frames, step={args.frame_step_days}d)\n"
    )

    # ── First pass: compute all frames to find global limits ───────────────
    frame_records: list[dict] = []
    prev_nodes: Optional[list[str]] = None
    prev_xy: Optional[np.ndarray] = None

    all_z_vals: list[float] = []
    all_col_vals: list[float] = []
    all_xy: list[np.ndarray] = []

    print("Pass 1/2: computing frame data …")
    t0 = time.perf_counter()

    for fi, date in enumerate(render_dates):
        cache_path = frames_dir / f"frame_{fi:04d}.npz"
        if not args.no_cache and cache_path.exists():
            try:
                d = np.load(cache_path, allow_pickle=True)
                all_z_vals.extend(d["anchor_z"].tolist())
                all_col_vals.extend(d["anchor_color"].tolist())
                all_xy.append(np.stack([d["anchor_x"], d["anchor_y"]], 1))
                frame_records.append(
                    {"frame_idx": fi, "path": str(cache_path), "date": str(d["date"])}
                )
                print(f"  [{fi:03d}] {date.date()} — cache hit")
                continue
            except Exception:
                pass

        # Find nearest signal date
        try:
            snap = nearest_prior(sigs["date"], date)
        except ValueError:
            print(f"  [{fi:03d}] {date.date()} — no prior signal date, skip")
            continue

        sig_d = sigs[sigs["date"] == snap].copy()
        if sig_d.empty:
            print(f"  [{fi:03d}] {date.date()} — no signals, skip")
            continue

        short_d = None
        if short_sigs is not None:
            short_d = short_sigs[short_sigs["date"] == snap].copy()
            if short_d.empty:
                short_d = None

        # Return index
        m = np.where(all_dates == snap)[0]
        if len(m) == 0:
            el = np.where(all_dates <= snap)[0]
            if len(el) == 0:
                print(f"  [{fi:03d}] {date.date()} — no return date, skip")
                continue
            di = int(el[-1])
        else:
            di = int(m[0])

        # Nodes
        nodes, long_set, short_set = build_nodes(
            sig_d,
            short_d,
            args.top_signals,
            args.max_nodes,
            t2i,
            args.extra_node_mode,
            args.extra_nodes,
            returns,
            all_tickers,
            di,
            args.lookback,
            args.forward_days,
        )
        if len(nodes) < 8:
            print(f"  [{fi:03d}] {date.date()} — too few nodes ({len(nodes)}), skip")
            continue

        # Window + coverage filter
        si = max(0, di - args.lookback + 1)
        nidx = [t2i[t] for t in nodes]
        win = returns[si : di + 1, :][:, nidx].copy()
        fr = np.isfinite(win).mean(0)
        keep = fr >= 0.75
        nodes = [n for n, k in zip(nodes, keep) if k]
        nidx = [i for i, k in zip(nidx, keep) if k]
        win = win[:, keep]
        if len(nodes) < 8:
            print(f"  [{fi:03d}] {date.date()} — too few after coverage filter, skip")
            continue

        # Fill NaN
        cm = np.nanmean(win, 0)
        nm = ~np.isfinite(win)
        win[nm] = np.take(cm, np.where(nm)[1])

        # Corr + MDS  [PERF: hotspot — replace with Rust/rayon binary later]
        corr = corrcoef_fast(win).astype(np.float32)
        corr = np.nan_to_num(corr)
        coords = classical_mds(corr)

        # Procrustes
        if prev_xy is not None and prev_nodes is not None:
            coords = procrustes_align(prev_xy, coords, prev_nodes, nodes)

        x_a, y_a = coords[:, 0], coords[:, 1]

        # Signal maps
        sig_map = (
            sig_d.sort_values("adjusted_confidence", ascending=False)
            .drop_duplicates("ticker")
            .set_index("ticker")
        )
        short_map = (
            short_d.sort_values("adjusted_confidence", ascending=False)
            .drop_duplicates("ticker")
            .set_index("ticker")
            if short_d is not None
            else None
        )
        kw = dict(
            returns=returns,
            node_indices=nidx,
            date_idx=di,
            forward_days=args.forward_days,
            lookback=args.lookback,
        )
        z_a = (
            winsorize(
                compute_values(args.z_mode, nodes, sig_map, short_map, **kw),
                args.winsorize_z,
            )
            * args.z_scale
        )
        col_a = winsorize(
            compute_values(args.color_mode, nodes, sig_map, short_map, **kw),
            args.winsorize_color,
        )

        conf = np.zeros(len(nodes), np.float32)
        for ii, t in enumerate(nodes):
            if t in sig_map.index:
                conf[ii] = float(sig_map.loc[t, "adjusted_confidence"])
            elif short_map is not None and t in short_map.index:
                conf[ii] = float(short_map.loc[t, "adjusted_confidence"])

        is_long = np.array([n in long_set for n in nodes], dtype=np.uint8)
        is_short = np.array([n in short_set for n in nodes], dtype=np.uint8)

        # Grid interpolation  [PERF: RBF is O(N^3) — GPU RBF or sparse GP later]
        print(
            f"  [{fi:03d}] {snap.date()}  "
            f"nodes={len(nodes)} long={is_long.sum()} short={is_short.sum()} … ",
            end="",
            flush=True,
        )
        t_interp = time.perf_counter()
        GX, GY, GZ = interpolate_grid(
            x_a,
            y_a,
            z_a,
            args.grid_size,
            args.interpolation_method,
            args.smooth_sigma,
        )
        _, _, GC = interpolate_grid(
            x_a,
            y_a,
            col_a,
            args.grid_size,
            args.interpolation_method,
            args.smooth_sigma,
        )
        dt_interp = time.perf_counter() - t_interp
        print(f"interp {dt_interp:.2f}s")

        # Context info
        ctx_regime = "UNKNOWN"
        ctx_vol_z = 0.0
        ctx_ent_z = 0.0
        if context_df is not None:
            try:
                ctx_row = context_df[context_df["date"] == snap]
                if not ctx_row.empty:
                    r = ctx_row.iloc[0]
                    ctx_regime = str(r.get("regime", "UNKNOWN"))
                    ctx_vol_z = float(r.get("vol_zscore", 0.0))
                    ctx_ent_z = float(r.get("entropy_z", 0.0))
            except Exception:
                pass

        np.savez_compressed(
            cache_path,
            # Fixed per frame
            date=np.array(str(snap.date())),
            # Anchor node arrays
            anchor_x=x_a.astype(np.float32),
            anchor_y=y_a.astype(np.float32),
            anchor_z=z_a.astype(np.float32),
            anchor_color=col_a.astype(np.float32),
            anchor_conf=conf.astype(np.float32),
            is_long=is_long,
            is_short=is_short,
            tickers=np.array(nodes),
            # Grid arrays (interpolated, smoothed)
            grid_x=GX.astype(np.float32),
            grid_y=GY.astype(np.float32),
            grid_z=GZ.astype(np.float32),
            grid_color=GC.astype(np.float32),
            # Context
            ctx_regime=np.array(ctx_regime),
            ctx_vol_z=np.array(ctx_vol_z),
            ctx_ent_z=np.array(ctx_ent_z),
        )

        all_z_vals.extend(z_a[np.isfinite(z_a)].tolist())
        all_col_vals.extend(col_a[np.isfinite(col_a)].tolist())

        if np.isfinite(GZ).any():
            all_z_vals.extend(GZ[np.isfinite(GZ)].ravel().tolist())

        if np.isfinite(GC).any():
            all_col_vals.extend(GC[np.isfinite(GC)].ravel().tolist())

        all_xy.append(coords)
        frame_records.append(
            {"frame_idx": fi, "path": str(cache_path), "date": str(snap.date())}
        )
        prev_nodes, prev_xy = nodes, coords

    elapsed = time.perf_counter() - t0
    print(f"\nPass 1 done in {elapsed:.1f}s  ({len(frame_records)} frames built)")

    if not frame_records:
        print("ERROR: No frames built. Check date range and signal file.")
        return

    # ── Global limits (for fixed-limit animation) ──────────────────────────
    z_arr = np.array(all_z_vals, dtype=np.float32)
    col_arr = np.array(all_col_vals, dtype=np.float32)

    def pct(a, lo, hi):
        return float(np.nanpercentile(a, lo)), float(np.nanpercentile(a, hi))

    z_lim = pct(z_arr, 1, 99)
    col_lim = pct(col_arr, 1, 99)

    # Also compute global x/y range from all anchor positions
    if all_xy:
        xy_all = np.vstack(all_xy)
        xy_lim = (
            float(xy_all[:, 0].min()),
            float(xy_all[:, 0].max()),
            float(xy_all[:, 1].min()),
            float(xy_all[:, 1].max()),
        )
    else:
        xy_lim = (-1.0, 1.0, -1.0, 1.0)

    # ── Manifest ───────────────────────────────────────────────────────────
    manifest = {
        "version": "2",
        "created": pd.Timestamp.now().isoformat(),
        "parameters": {
            "returns_meta": args.returns_meta,
            "signals": args.signals,
            "short_signals": args.short_signals,
            "start_date": args.start_date,
            "end_date": args.end_date,
            "frame_step_days": args.frame_step_days,
            "lookback": args.lookback,
            "forward_days": args.forward_days,
            "top_signals": args.top_signals,
            "max_nodes": args.max_nodes,
            "extra_node_mode": args.extra_node_mode,
            "extra_nodes": args.extra_nodes,
            "grid_size": args.grid_size,
            "smooth_sigma": args.smooth_sigma,
            "z_mode": args.z_mode,
            "color_mode": args.color_mode,
            "interpolation_method": args.interpolation_method,
        },
        "global_limits": {
            "z_min": z_lim[0],
            "z_max": z_lim[1],
            "color_min": col_lim[0],
            "color_max": col_lim[1],
            "x_min": xy_lim[0],
            "x_max": xy_lim[1],
            "y_min": xy_lim[2],
            "y_max": xy_lim[3],
        },
        "grid_size": args.grid_size,
        "n_frames": len(frame_records),
        "frames": frame_records,
    }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\n✓  manifest:  {manifest_path}")
    print(f"✓  {len(frame_records)} frames in {frames_dir}")
    print(f"\n   z_lim:     [{z_lim[0]:.4f}, {z_lim[1]:.4f}]")
    print(f"   color_lim: [{col_lim[0]:.4f}, {col_lim[1]:.4f}]")
    print(f"\nTo visualize:")
    print(f"  python scripts/visualize_market_fabric_vispy.py \\")
    print(f"    --frames-dir {out_dir} --ticker-labels")


if __name__ == "__main__":
    main()
