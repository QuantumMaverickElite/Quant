"""
render_market_fabric_v2.py
==========================
Market Fabric Manifold v2 — smooth, dense, interpolated terrain surface.

UPGRADE FROM v1
---------------
v1 triangulated directly from sparse stock anchors (36-50 nodes), producing
flat low-poly panels. v2 instead:

  1. Embeds selected stock anchors into 2D correlation space (MDS).
  2. Interpolates z and color values from those anchors onto a dense regular
     grid (--grid-size × --grid-size, default 180×180).
  3. Smooths the grid with a Gaussian filter (--smooth-sigma).
  4. Masks grid cells too far from any anchor so the surface does not stretch
     into empty space.
  5. Renders the dense grid as matplotlib plot_surface or Plotly Surface —
     a true smooth fabric, not a mesh of polygons.
  6. Overlays the anchor stock nodes on top as small dots + labels.

HOW IT WORKS
------------
CORRELATION CREATES THE FABRIC
  Rolling returns over --lookback days → correlation matrix → Mantegna distance
  d = sqrt(0.5*(1-corr)) → Classical MDS embedding into (x, y).
  Highly correlated stocks cluster together; uncorrelated ones drift apart.

Z-MODE CONTROLS HEIGHT (valleys / spikes)
  peer_spread_z  : long anchors → valleys; short anchors → spikes.
  forward_return : realized cumulative return over next N days.
  volatility     : annualized realized volatility.
  confidence     : adjusted_confidence from signal file.

COLOR-MODE CONTROLS HEAT (independent from z)
  Same choices as z-mode. Typical: z=peer_spread_z + color=forward_return
  shows signal shape heated by realized outcome.

GRID INTERPOLATION (the key upgrade)
  Preferred: scipy.interpolate.RBFInterpolator (smooth, handles sparse data).
  Fallback: scipy.interpolate.griddata (linear/cubic/nearest).
  Fallback: matplotlib triangulation if scipy missing.
  After interpolation: scipy.ndimage.gaussian_filter smooths the grid.
  Masking: scipy.spatial.cKDTree finds nearest anchor for every grid cell;
  cells farther than the 85th-percentile inter-anchor distance are masked NaN
  so the surface does not spread beyond the market cloud.

PROCRUSTES ALIGNMENT (animation)
  MDS is defined up to rotation/reflection. Procrustes aligns each new frame
  to the previous one on shared tickers, so the fabric evolves smoothly.

TEMPORAL SMOOTHING (animation, --temporal-smoothing > 0)
  Grid values are blended with the previous frame:
    grid_z = alpha * prev_grid_z + (1-alpha) * new_grid_z
  where alpha = --temporal-smoothing. Keeps the fabric from flickering.

GPU ACCELERATION
  CuPy handles correlation matrix and MDS eigendecomposition if available.
  # FUTURE: move rolling correlation + MDS into Rust/rayon binary here.

EXTRA NODES (--extra-node-mode)
  Beyond signal anchors + their peers, additional tickers can be added:
  volatile  : top N by realized volatility.
  movers    : top N by |forward_return| (or recent absolute return).
  mixed     : half volatile, half movers.
  These fill the grid so the surface has more anchors and fewer holes.

CACHE
  Per-frame data is saved to cache/ as .npz files including:
  x, y, z, color, grid_x, grid_y, grid_z, grid_color, node metadata arrays.
  Cache key includes all parameters so changing any arg invalidates it.

OUTPUTS
-------
outputs/reports/plots/market_fabric_v2/
  fabric_YYYY-MM-DD_<z>_<color>.png
  fabric_YYYY-MM-DD_<z>_<color>_nodes.csv
  interactive_YYYY-MM-DD_<z>_<color>.html   (if --interactive)
  frames/frame_0000.png ...                  (if --animate)
  cache/frame_<tag>.npz

EXAMPLE COMMANDS
----------------
# Static snapshot:
python scripts/render_market_fabric_v2.py \\
  --returns-meta /tmp/quant_returns/.../returns_meta.json \\
  --signals outputs/signals/large_universe_peer_spread_long_top5_v1.parquet \\
  --date 2020-03-24 --out-dir outputs/reports/plots/market_fabric_v2 \\
  --lookback 126 --forward-days 60 --top-signals 8 --max-nodes 400 \\
  --extra-node-mode mixed --extra-nodes 250 \\
  --grid-size 200 --smooth-sigma 2.0 \\
  --z-mode peer_spread_z --color-mode forward_return \\
  --surface-mode smooth --interactive

# Animation:
python scripts/render_market_fabric_v2.py ... \\
  --animate --start-date 2020-01-01 --end-date 2020-06-30 \\
  --frame-step-days 5 --temporal-smoothing 0.35 --fixed-limits
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ── Optional accelerators ────────────────────────────────────────────────────
try:
    import cupy as cp

    CUPY_AVAILABLE = True
except ImportError:
    cp = None
    CUPY_AVAILABLE = False

try:
    from scipy.spatial import Delaunay, cKDTree
    from scipy.interpolate import RBFInterpolator, griddata
    from scipy.ndimage import gaussian_filter

    SCIPY_AVAILABLE = True
    SCIPY_RBF = True
except ImportError:
    try:
        from scipy.spatial import Delaunay, cKDTree
        from scipy.interpolate import griddata
        from scipy.ndimage import gaussian_filter

        SCIPY_AVAILABLE = True
        SCIPY_RBF = False
        RBFInterpolator = None
    except ImportError:
        SCIPY_AVAILABLE = False
        SCIPY_RBF = False
        Delaunay = cKDTree = RBFInterpolator = griddata = gaussian_filter = None

try:
    import plotly.graph_objects as go

    PLOTLY_AVAILABLE = True
except ImportError:
    go = None
    PLOTLY_AVAILABLE = False

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from matplotlib.colors import Normalize, LightSource
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # ── Data inputs ───────────────────────────────────────────────────────
    p.add_argument("--returns-meta", required=True)
    p.add_argument("--signals", required=True, help="Parquet: peer-spread long signals")
    p.add_argument(
        "--short-signals",
        default=None,
        help="Parquet: peer-spread short candidates (optional)",
    )
    p.add_argument("--context", default=None, help="Parquet: market context (optional)")
    p.add_argument("--out-dir", required=True)

    # ── Date selection ────────────────────────────────────────────────────
    p.add_argument("--date", default=None, help="Snapshot date YYYY-MM-DD")
    p.add_argument("--animate", action="store_true")
    p.add_argument("--start-date", default=None)
    p.add_argument("--end-date", default=None)
    p.add_argument("--frame-step-days", type=int, default=5)

    # ── Node selection ────────────────────────────────────────────────────
    p.add_argument("--lookback", type=int, default=126)
    p.add_argument("--forward-days", type=int, default=60)
    p.add_argument("--top-signals", type=int, default=8)
    p.add_argument(
        "--max-nodes", type=int, default=400, help="Hard cap on total anchor nodes"
    )
    p.add_argument(
        "--extra-node-mode",
        choices=["none", "volatile", "movers", "mixed"],
        default="mixed",
        help="How to fill remaining node budget beyond signal+peers",
    )
    p.add_argument(
        "--extra-nodes",
        type=int,
        default=250,
        help="Max extra nodes to add beyond signal+peers",
    )

    # ── Surface quality ───────────────────────────────────────────────────
    p.add_argument(
        "--grid-size",
        type=int,
        default=180,
        help="Resolution of interpolated grid (N×N)",
    )
    p.add_argument(
        "--smooth-sigma",
        type=float,
        default=1.5,
        help="Gaussian smoothing sigma on grid (0=off)",
    )
    p.add_argument(
        "--interpolation-method",
        choices=["rbf", "linear", "cubic", "nearest"],
        default="rbf",
        help="Grid interpolation method",
    )
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
        "--surface-mode",
        choices=["smooth", "trisurf", "scatter"],
        default="smooth",
        help="smooth=dense interpolated grid; trisurf=low-poly; scatter=fallback",
    )
    p.add_argument(
        "--z-scale", type=float, default=1.0, help="Vertical exaggeration multiplier"
    )
    p.add_argument(
        "--winsorize-z",
        type=float,
        default=0.02,
        help="Winsorize z values at this tail fraction (0=off)",
    )
    p.add_argument(
        "--winsorize-color",
        type=float,
        default=0.02,
        help="Winsorize color values at this tail fraction (0=off)",
    )

    # ── Animation quality ─────────────────────────────────────────────────
    p.add_argument(
        "--temporal-smoothing",
        type=float,
        default=0.0,
        help="Exponential smoothing alpha across frames [0=off, 0.3-0.5=smooth]",
    )
    p.add_argument(
        "--fixed-camera",
        action="store_true",
        help="Lock camera angle across all frames",
    )
    p.add_argument(
        "--fixed-limits",
        action="store_true",
        help="Lock x/y/z/color axis limits across all frames (compute on first frame)",
    )

    # ── Output ────────────────────────────────────────────────────────────
    p.add_argument(
        "--interactive", action="store_true", help="Write interactive HTML via Plotly"
    )
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--dpi", type=int, default=170)

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


def nearest_prior_date(
    dates_series: pd.Series, requested: pd.Timestamp
) -> pd.Timestamp:
    eligible = dates_series[dates_series <= requested]
    if eligible.empty:
        raise ValueError(f"No dates on or before {requested.date()}.")
    return eligible.max()


# ═════════════════════════════════════════════════════════════════════════════
# MATH: CORRELATION / MDS / PROCRUSTES
# ═════════════════════════════════════════════════════════════════════════════


def gpu_corrcoef(window: np.ndarray) -> np.ndarray:
    """Correlation matrix. Uses CuPy if available.
    # FUTURE: replace with Rust/rayon rolling-corr binary for large windows.
    """
    if not CUPY_AVAILABLE:
        return np.corrcoef(window, rowvar=False)
    try:
        w = cp.asarray(window, dtype=cp.float32)
        w = w - w.mean(axis=0, keepdims=True)
        norms = cp.linalg.norm(w, axis=0, keepdims=True).clip(1e-12)
        wn = w / norms
        return cp.asnumpy(wn.T @ wn)
    except Exception as e:
        warnings.warn(f"CuPy corrcoef failed ({e}); falling back to NumPy.")
        return np.corrcoef(window, rowvar=False)


def classical_mds(corr: np.ndarray, dims: int = 2) -> np.ndarray:
    """Classical MDS from correlation matrix.
    # FUTURE: GPU eigh via CuPy already used; Rust embedding possible later.
    """
    corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
    corr = np.clip(corr, -0.9999, 0.9999)
    dist2 = 0.5 * (1.0 - corr)
    n = dist2.shape[0]
    H = np.eye(n) - np.ones((n, n)) / n
    gram = -0.5 * (H @ dist2 @ H)
    if CUPY_AVAILABLE:
        try:
            vals_g, vecs_g = cp.linalg.eigh(cp.asarray(gram.astype(np.float64)))
            vals, vecs = cp.asnumpy(vals_g), cp.asnumpy(vecs_g)
        except Exception as e:
            warnings.warn(f"CuPy eigh failed ({e}); falling back to NumPy.")
            vals, vecs = np.linalg.eigh(gram)
    else:
        vals, vecs = np.linalg.eigh(gram)
    order = np.argsort(vals)[::-1]
    vals = np.maximum(vals[order][:dims], 0.0)
    vecs = vecs[:, order][:, :dims]
    return (vecs * np.sqrt(vals + 1e-12)).astype(np.float32)


def procrustes_align(
    ref_xy: np.ndarray, new_xy: np.ndarray, ref_nodes: list[str], new_nodes: list[str]
) -> np.ndarray:
    """Rotate/reflect new_xy to best match ref_xy on shared tickers."""
    shared = list(set(ref_nodes) & set(new_nodes))
    if len(shared) < 3:
        return new_xy
    ri = [ref_nodes.index(t) for t in shared]
    ni = [new_nodes.index(t) for t in shared]
    A = ref_xy[ri] - ref_xy[ri].mean(0)
    B = new_xy[ni] - new_xy[ni].mean(0)
    U, _, Vt = np.linalg.svd(A.T @ B)
    R = (U @ Vt).T
    c_b = new_xy[ni].mean(0)
    c_a = ref_xy[ri].mean(0)
    return ((new_xy - c_b) @ R + c_a).astype(np.float32)


# ═════════════════════════════════════════════════════════════════════════════
# NODE SELECTION (signal anchors + extra fill nodes)
# ═════════════════════════════════════════════════════════════════════════════


def build_node_set(
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
    """
    Build anchor node list.
    Priority: long signals → their peers → short signals → their peers → extras.
    Extra modes add high-vol or big-mover tickers to fill out the grid.
    """
    long_top = (
        sig_df.sort_values("adjusted_confidence", ascending=False)
        .drop_duplicates("ticker")
        .head(top_signals)
    )
    long_tickers = set(long_top["ticker"].astype(str).str.upper())

    short_top = pd.DataFrame()
    short_tickers: set[str] = set()
    if short_df is not None and len(short_df) > 0:
        short_top = (
            short_df.sort_values("adjusted_confidence", ascending=False)
            .drop_duplicates("ticker")
            .head(top_signals)
        )
        short_tickers = set(short_top["ticker"].astype(str).str.upper())

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
        for peer in str(row.get("peer_list", "")).split("|"):
            add(peer)
    for _, row in short_top.iterrows():
        add(row["ticker"])
        for peer in str(row.get("peer_list", "")).split("|"):
            add(peer)

    # ── Extra nodes to densify the grid ──────────────────────────────────
    if extra_mode != "none" and len(nodes) < max_nodes and extra_budget > 0:
        start_idx = max(0, date_idx - lookback + 1)
        # sample up to 1000 universe tickers to avoid huge matrix
        candidate_tickers = [t for t in all_tickers if t not in seen]
        rng = np.random.default_rng(42)
        if len(candidate_tickers) > 1200:
            candidate_tickers = rng.choice(
                candidate_tickers, 1200, replace=False
            ).tolist()

        cand_idx = [ticker_to_idx[t] for t in candidate_tickers]
        window = returns[start_idx : date_idx + 1, :][:, cand_idx]
        finite_rate = np.isfinite(window).mean(axis=0)
        cand_ok = [t for t, f in zip(candidate_tickers, finite_rate) if f >= 0.75]
        cand_ok_idx = [ticker_to_idx[t] for t in cand_ok]
        window_ok = returns[start_idx : date_idx + 1, :][:, cand_ok_idx]

        scores_vol = np.nanstd(window_ok, axis=0)  # volatility proxy

        if extra_mode in ("movers", "mixed"):
            future_end = min(returns.shape[0], date_idx + forward_days + 1)
            future = returns[date_idx + 1 : future_end, :][:, cand_ok_idx]
            scores_move = np.abs(np.nansum(future, axis=0))
        else:
            scores_move = scores_vol.copy()

        if extra_mode == "volatile":
            scores = scores_vol
        elif extra_mode == "movers":
            scores = scores_move
        else:  # mixed
            v_norm = scores_vol / (scores_vol.max() + 1e-9)
            m_norm = scores_move / (scores_move.max() + 1e-9)
            scores = 0.5 * v_norm + 0.5 * m_norm

        order = np.argsort(scores)[::-1]
        added = 0
        for i in order:
            if added >= extra_budget:
                break
            if add(cand_ok[i]):
                added += 1

    return nodes[:max_nodes], long_tickers, short_tickers


# ═════════════════════════════════════════════════════════════════════════════
# VALUE COMPUTATION (z and color)
# ═════════════════════════════════════════════════════════════════════════════


def compute_values(
    mode: str,
    nodes: list[str],
    signal_map: Optional[pd.DataFrame],
    short_map: Optional[pd.DataFrame],
    returns: np.ndarray,
    node_indices: list[int],
    date_idx: int,
    forward_days: int,
    lookback: int,
) -> np.ndarray:
    n = len(nodes)
    vals = np.zeros(n, dtype=np.float32)

    if mode == "peer_spread_z":
        for i, t in enumerate(nodes):
            if signal_map is not None and t in signal_map.index:
                vals[i] = float(signal_map.loc[t, "peer_spread_z"])
            elif short_map is not None and t in short_map.index:
                vals[i] = float(short_map.loc[t, "peer_spread_z"])

    elif mode == "forward_return":
        future_end = min(returns.shape[0], date_idx + forward_days + 1)
        future = returns[date_idx + 1 : future_end, :][:, node_indices]
        vals = np.nansum(future, axis=0).astype(np.float32)

    elif mode == "volatility":
        start_idx = max(0, date_idx - lookback + 1)
        w = returns[start_idx : date_idx + 1, :][:, node_indices]
        vals = (np.nanstd(w, axis=0) * np.sqrt(252)).astype(np.float32)

    elif mode == "confidence":
        for i, t in enumerate(nodes):
            if signal_map is not None and t in signal_map.index:
                vals[i] = float(signal_map.loc[t, "adjusted_confidence"])
            elif short_map is not None and t in short_map.index:
                vals[i] = float(short_map.loc[t, "adjusted_confidence"])

    return vals


def winsorize(arr: np.ndarray, frac: float) -> np.ndarray:
    if frac <= 0:
        return arr
    lo = np.nanpercentile(arr, frac * 100)
    hi = np.nanpercentile(arr, (1 - frac) * 100)
    return np.clip(arr, lo, hi)


# ═════════════════════════════════════════════════════════════════════════════
# GRID INTERPOLATION (the key upgrade over v1)
# ═════════════════════════════════════════════════════════════════════════════


def interpolate_to_grid(
    x: np.ndarray,
    y: np.ndarray,
    values: np.ndarray,
    grid_size: int,
    method: str,
    smooth_sigma: float,
    mask_percentile: float = 85.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Interpolate scattered (x,y,values) onto a dense grid_size×grid_size grid.

    Returns (grid_x, grid_y, grid_z) where grid_z is NaN outside the market cloud.

    Masking: uses cKDTree to find nearest anchor for every grid cell.
    Cells farther than the mask_percentile-th inter-point distance are set NaN.

    # FUTURE: the RBF solve is O(n^3). For n>500, replace with a sparse
    #   approximation or move to a GPU-accelerated RBF (cuML / custom CUDA).
    """
    pad = 0.08
    xmin, xmax = x.min() - pad * (x.max() - x.min()), x.max() + pad * (
        x.max() - x.min()
    )
    ymin, ymax = y.min() - pad * (y.max() - y.min()), y.max() + pad * (
        y.max() - y.min()
    )

    gx = np.linspace(xmin, xmax, grid_size)
    gy = np.linspace(ymin, ymax, grid_size)
    grid_x, grid_y = np.meshgrid(gx, gy)

    pts = np.stack([x, y], axis=1).astype(np.float64)
    vals = values.astype(np.float64)
    grid_pts = np.stack([grid_x.ravel(), grid_y.ravel()], axis=1)

    # ── Attempt RBF ───────────────────────────────────────────────────────
    grid_z_flat = None
    if SCIPY_RBF and method == "rbf" and RBFInterpolator is not None:
        try:
            # thin_plate_spline is smooth and well-conditioned
            rbf = RBFInterpolator(pts, vals, kernel="thin_plate_spline", smoothing=0.5)
            grid_z_flat = rbf(grid_pts).astype(np.float32)
        except Exception as e:
            warnings.warn(f"RBFInterpolator failed ({e}); falling back to griddata.")

    # ── Fallback: griddata ─────────────────────────────────────────────────
    if grid_z_flat is None and SCIPY_AVAILABLE:
        gd_method = method if method != "rbf" else "cubic"
        try:
            grid_z_flat = griddata(
                pts, vals, grid_pts, method=gd_method, fill_value=np.nan
            ).astype(np.float32)
            # Fill remaining NaN holes with nearest
            nan_mask = ~np.isfinite(grid_z_flat)
            if nan_mask.any():
                fill = griddata(pts, vals, grid_pts[nan_mask], method="nearest").astype(
                    np.float32
                )
                grid_z_flat[nan_mask] = fill
        except Exception as e:
            warnings.warn(f"griddata failed ({e}); using trisurf fallback.")

    # ── Final fallback: linear interp via matplotlib triangulation ─────────
    if grid_z_flat is None:
        tri = mtri.Triangulation(x.astype(float), y.astype(float))
        interp = mtri.LinearTriInterpolator(tri, vals.astype(float))
        grid_z_flat = np.array(interp(grid_x, grid_y), dtype=np.float32).ravel()

    grid_z = grid_z_flat.reshape(grid_size, grid_size)

    # ── Gaussian smoothing ─────────────────────────────────────────────────
    if smooth_sigma > 0 and gaussian_filter is not None:
        # Replace NaN with zero before filtering, restore mask after
        nan_before = ~np.isfinite(grid_z)
        tmp = np.where(np.isfinite(grid_z), grid_z, 0.0)
        tmp = gaussian_filter(tmp.astype(np.float64), sigma=smooth_sigma).astype(
            np.float32
        )
        grid_z = np.where(nan_before, np.nan, tmp)

    # ── Distance mask: hide cells far from any anchor ──────────────────────
    if SCIPY_AVAILABLE and cKDTree is not None:
        tree = cKDTree(pts)
        dists, _ = tree.query(grid_pts, k=1)
        # Compute typical anchor spacing as reference
        if len(pts) > 1:
            nn_dists, _ = tree.query(pts, k=min(2, len(pts)))
            nn_spacing = nn_dists[:, -1] if nn_dists.ndim == 2 else nn_dists
            threshold = np.percentile(nn_spacing[nn_spacing > 0], mask_percentile) * 3.5
        else:
            threshold = np.inf
        far_mask = dists.reshape(grid_size, grid_size) > threshold
        grid_z = np.where(far_mask, np.nan, grid_z)
    else:
        # Simple convex-hull mask via bounding polygon approximation
        pass  # leave as-is; scipy unavailable

    return grid_x.astype(np.float32), grid_y.astype(np.float32), grid_z


# ═════════════════════════════════════════════════════════════════════════════
# FRAME DATA COMPUTATION (with .npz cache)
# ═════════════════════════════════════════════════════════════════════════════


def _cache_tag(date: pd.Timestamp, args: argparse.Namespace) -> str:
    return (
        f"{date.date()}_{args.z_mode}_{args.color_mode}"
        f"_lb{args.lookback}_fw{args.forward_days}"
        f"_n{args.max_nodes}_s{args.top_signals}"
        f"_g{args.grid_size}_sm{args.smooth_sigma:.1f}"
        f"_ex{args.extra_node_mode}{args.extra_nodes}"
        f"_im{args.interpolation_method}"
    )


def compute_frame(
    date: pd.Timestamp,
    returns: np.ndarray,
    all_dates: pd.DatetimeIndex,
    all_tickers: list[str],
    signals: pd.DataFrame,
    short_signals: Optional[pd.DataFrame],
    ticker_to_idx: dict,
    args: argparse.Namespace,
    cache_dir: Path,
    prev_frame: Optional[dict],
) -> Optional[dict]:
    """
    Compute one fully-interpolated frame.
    Returns dict with: nodes, long_tickers, short_tickers, x, y, z, color,
    confidence, is_long, is_short, grid_x, grid_y, grid_z, grid_color,
    snapshot_date, corr (may be None if cached).
    """
    tag = _cache_tag(date, args)
    cache_path = cache_dir / f"frame_{tag}.npz"

    if not args.no_cache and cache_path.exists():
        try:
            d = np.load(cache_path, allow_pickle=True)
            frame = {k: d[k] for k in d.files}
            frame["nodes"] = frame["nodes"].tolist()
            frame["long_tickers"] = set(frame["long_tickers"].tolist())
            frame["short_tickers"] = set(frame["short_tickers"].tolist())
            frame["snapshot_date"] = pd.Timestamp(str(frame["snapshot_date"]))
            frame["corr"] = None
            # Re-apply Procrustes if we have a previous frame
            if prev_frame is not None:
                coords = np.stack([frame["x"], frame["y"]], axis=1)
                aligned = procrustes_align(
                    np.stack([prev_frame["x"], prev_frame["y"]], axis=1),
                    coords,
                    prev_frame["nodes"],
                    frame["nodes"],
                )
                frame["x"], frame["y"] = aligned[:, 0], aligned[:, 1]
                # Re-interpolate grid on aligned coords
                frame["grid_x"], frame["grid_y"], frame["grid_z"] = interpolate_to_grid(
                    frame["x"],
                    frame["y"],
                    frame["z"],
                    args.grid_size,
                    args.interpolation_method,
                    args.smooth_sigma,
                )
                frame["grid_x"], frame["grid_y"], frame["grid_color"] = (
                    interpolate_to_grid(
                        frame["x"],
                        frame["y"],
                        frame["color"],
                        args.grid_size,
                        args.interpolation_method,
                        args.smooth_sigma,
                    )
                )
            return frame
        except Exception as e:
            warnings.warn(f"Cache load failed ({e}); recomputing.")

    # ── Find snapshot date ─────────────────────────────────────────────────
    snap_date = nearest_prior_date(signals["date"], date)
    sig_on_date = signals[signals["date"] == snap_date].copy()
    if len(sig_on_date) == 0:
        return None

    short_on_date = None
    if short_signals is not None:
        short_on_date = short_signals[short_signals["date"] == snap_date].copy()
        if len(short_on_date) == 0:
            short_on_date = None

    # ── Return index ───────────────────────────────────────────────────────
    matches = np.where(all_dates == snap_date)[0]
    if len(matches) == 0:
        eligible = np.where(all_dates <= snap_date)[0]
        if len(eligible) == 0:
            return None
        date_idx = int(eligible[-1])
    else:
        date_idx = int(matches[0])

    # ── Build node set ─────────────────────────────────────────────────────
    nodes, long_tickers, short_tickers = build_node_set(
        sig_df=sig_on_date,
        short_df=short_on_date,
        top_signals=args.top_signals,
        max_nodes=args.max_nodes,
        ticker_to_idx=ticker_to_idx,
        extra_mode=args.extra_node_mode,
        extra_budget=args.extra_nodes,
        returns=returns,
        all_tickers=all_tickers,
        date_idx=date_idx,
        lookback=args.lookback,
        forward_days=args.forward_days,
    )
    if len(nodes) < 8:
        return None

    # ── Return window + coverage filter ───────────────────────────────────
    start_idx = max(0, date_idx - args.lookback + 1)
    node_indices = [ticker_to_idx[t] for t in nodes]
    window = returns[start_idx : date_idx + 1, :][:, node_indices].copy()

    finite_rate = np.isfinite(window).mean(axis=0)
    keep = finite_rate >= 0.75
    nodes = [n for n, k in zip(nodes, keep) if k]
    node_indices = [i for i, k in zip(node_indices, keep) if k]
    window = window[:, keep]
    if len(nodes) < 8:
        return None

    # Fill NaN
    col_means = np.nanmean(window, axis=0)
    nan_mask_w = ~np.isfinite(window)
    window[nan_mask_w] = np.take(col_means, np.where(nan_mask_w)[1])

    # ── Correlation + MDS ──────────────────────────────────────────────────
    corr = gpu_corrcoef(window)
    corr = np.nan_to_num(corr, nan=0.0).astype(np.float32)
    coords = classical_mds(corr, dims=2)

    # Procrustes alignment to previous frame
    if prev_frame is not None:
        coords = procrustes_align(
            np.stack([prev_frame["x"], prev_frame["y"]], axis=1),
            coords,
            prev_frame["nodes"],
            nodes,
        )

    x, y = coords[:, 0], coords[:, 1]

    # ── Signal lookup maps ─────────────────────────────────────────────────
    signal_map = (
        sig_on_date.sort_values("adjusted_confidence", ascending=False)
        .drop_duplicates("ticker")
        .set_index("ticker")
    )
    short_map = (
        short_on_date.sort_values("adjusted_confidence", ascending=False)
        .drop_duplicates("ticker")
        .set_index("ticker")
        if short_on_date is not None
        else None
    )

    kw = dict(
        returns=returns,
        node_indices=node_indices,
        date_idx=date_idx,
        forward_days=args.forward_days,
        lookback=args.lookback,
    )

    z = (
        winsorize(
            compute_values(args.z_mode, nodes, signal_map, short_map, **kw),
            args.winsorize_z,
        )
        * args.z_scale
    )
    color = winsorize(
        compute_values(args.color_mode, nodes, signal_map, short_map, **kw),
        args.winsorize_color,
    )

    confidence = np.zeros(len(nodes), dtype=np.float32)
    for i, t in enumerate(nodes):
        if t in signal_map.index:
            confidence[i] = float(signal_map.loc[t, "adjusted_confidence"])
        elif short_map is not None and t in short_map.index:
            confidence[i] = float(short_map.loc[t, "adjusted_confidence"])

    is_long = np.array([n in long_tickers for n in nodes], dtype=bool)
    is_short = np.array([n in short_tickers for n in nodes], dtype=bool)

    # ── Grid interpolation ─────────────────────────────────────────────────
    print(
        f"  interpolating grid ({args.grid_size}×{args.grid_size}) from {len(nodes)} anchors …"
    )
    grid_x, grid_y, grid_z = interpolate_to_grid(
        x,
        y,
        z,
        args.grid_size,
        args.interpolation_method,
        args.smooth_sigma,
    )
    _, _, grid_color = interpolate_to_grid(
        x,
        y,
        color,
        args.grid_size,
        args.interpolation_method,
        args.smooth_sigma,
    )

    frame = {
        "nodes": nodes,
        "long_tickers": long_tickers,
        "short_tickers": short_tickers,
        "x": x,
        "y": y,
        "z": z,
        "color": color,
        "confidence": confidence,
        "is_long": is_long,
        "is_short": is_short,
        "grid_x": grid_x,
        "grid_y": grid_y,
        "grid_z": grid_z,
        "grid_color": grid_color,
        "snapshot_date": snap_date,
        "corr": corr,
    }

    # ── Cache ──────────────────────────────────────────────────────────────
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        np.savez_compressed(
            cache_path,
            nodes=np.array(nodes),
            long_tickers=np.array(list(long_tickers)),
            short_tickers=np.array(list(short_tickers)),
            x=x,
            y=y,
            z=z,
            color=color,
            confidence=confidence,
            is_long=is_long,
            is_short=is_short,
            grid_x=grid_x,
            grid_y=grid_y,
            grid_z=grid_z,
            grid_color=grid_color,
            snapshot_date=np.array(str(snap_date)),
        )
        print(f"  cached: {cache_path.name}")
    except Exception as e:
        warnings.warn(f"Cache save failed: {e}")

    return frame


# ═════════════════════════════════════════════════════════════════════════════
# TEMPORAL SMOOTHING (animation)
# ═════════════════════════════════════════════════════════════════════════════


def apply_temporal_smoothing(
    frame: dict,
    prev_frame: Optional[dict],
    alpha: float,
) -> dict:
    """Blend grid_z and grid_color with previous frame's grid."""
    if prev_frame is None or alpha <= 0:
        return frame
    if frame["grid_z"].shape != prev_frame.get("grid_z", np.array([])).shape:
        return frame
    frame["grid_z"] = np.where(
        np.isfinite(frame["grid_z"]) & np.isfinite(prev_frame["grid_z"]),
        alpha * prev_frame["grid_z"] + (1 - alpha) * frame["grid_z"],
        frame["grid_z"],
    )
    frame["grid_color"] = np.where(
        np.isfinite(frame["grid_color"])
        & np.isfinite(prev_frame.get("grid_color", frame["grid_color"])),
        alpha * prev_frame["grid_color"] + (1 - alpha) * frame["grid_color"],
        frame["grid_color"],
    )
    return frame


# ═════════════════════════════════════════════════════════════════════════════
# MATPLOTLIB RENDER
# ═════════════════════════════════════════════════════════════════════════════

LONG_COLOR = "#00e5ff"  # cyan
SHORT_COLOR = "#ff4444"  # red
PEER_COLOR = "#555566"  # dark grey

_CMAP = plt.cm.RdYlGn


def _make_node_colors(is_long, is_short):
    return [
        LONG_COLOR if l else (SHORT_COLOR if s else PEER_COLOR)
        for l, s in zip(is_long, is_short)
    ]


def render_matplotlib(
    frame: dict,
    args: argparse.Namespace,
    out_path: Path,
    z_lim: Optional[tuple] = None,
    color_lim: Optional[tuple] = None,
    cam_elev: float = 28,
    cam_azim: float = -55,
) -> None:
    x, y, z = frame["x"], frame["y"], frame["z"]
    color = frame["color"]
    nodes = frame["nodes"]
    is_long, is_short = frame["is_long"], frame["is_short"]
    confidence = frame["confidence"]
    snap_date = frame["snapshot_date"]
    grid_x, grid_y, grid_z, grid_color = (
        frame["grid_x"],
        frame["grid_y"],
        frame["grid_z"],
        frame["grid_color"],
    )

    # ── Color normalization ───────────────────────────────────────────────
    finite_gc = grid_color[np.isfinite(grid_color)]
    c_min = (
        color_lim[0]
        if color_lim
        else (np.percentile(finite_gc, 2) if len(finite_gc) else -1)
    )
    c_max = (
        color_lim[1]
        if color_lim
        else (np.percentile(finite_gc, 98) if len(finite_gc) else 1)
    )
    if c_max <= c_min:
        c_max = c_min + 1e-6

    def norm_c(arr):
        return np.clip((arr - c_min) / (c_max - c_min), 0.0, 1.0)

    fig = plt.figure(figsize=(17, 11), facecolor="#080810")
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#080810")

    # ── Main surface ──────────────────────────────────────────────────────
    if args.surface_mode == "smooth" and grid_z is not None:
        # Map grid_color → RGBA surface colors
        gc_norm = norm_c(np.where(np.isfinite(grid_color), grid_color, c_min))
        face_colors = _CMAP(gc_norm)  # (H, W, 4)
        face_colors[..., 3] = 0.72  # semi-transparent fabric

        # Mask NaN regions as fully transparent
        nan_mask = ~np.isfinite(grid_z)
        face_colors[nan_mask, 3] = 0.0

        # plot_surface wants facecolors as (rows-1, cols-1, 4) for shading=flat
        # or (rows, cols, 4) for shading=gouraud — use gouraud for smoothness
        surf = ax.plot_surface(
            grid_x,
            grid_y,
            np.where(np.isfinite(grid_z), grid_z, np.nan),
            facecolors=face_colors,
            rstride=1,
            cstride=1,
            linewidth=0,
            antialiased=True,
            shade=True,
            lightsource=LightSource(azdeg=315, altdeg=35),
        )
        surf.set_edgecolor("none")

        # Fine mesh wireframe overlay (every Nth line)
        step = max(1, args.grid_size // 30)
        wf_alpha = 0.06
        for i in range(0, grid_size_safe(grid_x), step):
            row_z = np.where(np.isfinite(grid_z[i, :]), grid_z[i, :], np.nan)
            ax.plot(
                grid_x[i, :],
                grid_y[i, :],
                row_z,
                color="#ffffff",
                lw=0.15,
                alpha=wf_alpha,
            )
        for j in range(0, grid_size_safe(grid_x, axis=1), step):
            col_z = np.where(np.isfinite(grid_z[:, j]), grid_z[:, j], np.nan)
            ax.plot(
                grid_x[:, j],
                grid_y[:, j],
                col_z,
                color="#ffffff",
                lw=0.15,
                alpha=wf_alpha,
            )

    elif args.surface_mode == "trisurf":
        # Low-poly fallback: triangulate anchors directly
        from scipy.spatial import Delaunay as _D

        if SCIPY_AVAILABLE:
            tri = _D(np.stack([x, y], 1))
            simplices = tri.simplices
            fc = _CMAP(norm_c(color[simplices].mean(1)))
            fc[:, 3] = 0.55
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection

            verts = [list(zip(x[t], y[t], z[t])) for t in simplices]
            surf = mpl_toolkits.mplot3d.art3d.Poly3DCollection(
                verts, facecolors=fc, edgecolors="#ffffff", linewidths=0.08, alpha=0.55
            )
            ax.add_collection3d(surf)
            ax.auto_scale_xyz(x, y, z)
        else:
            tri_m = mtri.Triangulation(x.astype(float), y.astype(float))
            ax.plot_trisurf(x, y, z, triangulation=tri_m, cmap=_CMAP, alpha=0.55)

    else:
        ax.scatter(x, y, z, c=norm_c(color), cmap=_CMAP, s=18, alpha=0.7)

    # ── Anchor nodes (overlay on top of surface) ──────────────────────────
    is_signal = is_long | is_short
    # Raise nodes slightly above the surface so they are visible
    z_raise = np.where(np.isfinite(z), z, 0) + (
        (z.max() - z.min()) * 0.015 if z.max() != z.min() else 0.01
    )
    node_colors = _make_node_colors(is_long, is_short)
    sizes = np.where(
        is_long,
        85 + 55 * np.clip(confidence, 0, 1),
        np.where(is_short, 75 + 45 * np.clip(confidence, 0, 1), 12),
    )

    # Non-signal peers: tiny grey dots
    peer_mask = ~is_signal
    if peer_mask.any():
        ax.scatter(
            x[peer_mask],
            y[peer_mask],
            z_raise[peer_mask],
            c=PEER_COLOR,
            s=sizes[peer_mask],
            alpha=0.45,
            zorder=3,
            depthshade=False,
        )
    # Long / short signals: prominent colored markers
    for mask, col in [(is_long, LONG_COLOR), (is_short, SHORT_COLOR)]:
        if mask.any():
            ax.scatter(
                x[mask],
                y[mask],
                z_raise[mask],
                c=col,
                s=sizes[mask],
                alpha=0.95,
                zorder=6,
                edgecolors="#ffffff",
                linewidths=0.6,
                depthshade=False,
            )

    # ── Labels ────────────────────────────────────────────────────────────
    label_set = frame["long_tickers"] | frame["short_tickers"]
    z_span = float(np.nanmax(z) - np.nanmin(z)) if np.isfinite(z).any() else 1.0
    for i, node in enumerate(nodes):
        if node in label_set:
            sym = "▼" if is_long[i] else ("▲" if is_short[i] else "")
            ax.text(
                x[i],
                y[i],
                z_raise[i] + z_span * 0.06,
                f"{sym}{node}",
                fontsize=8,
                color=node_colors[i],
                fontweight="bold",
                ha="center",
                va="bottom",
                zorder=10,
            )

    # ── Axes styling ──────────────────────────────────────────────────────
    ax.view_init(elev=cam_elev, azim=cam_azim)
    if z_lim:
        ax.set_zlim(*z_lim)

    for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
        pane.fill = False
        pane.set_edgecolor("#1a1a2e")
    ax.grid(False)
    ax.tick_params(colors="#555566", labelsize=6.5)
    ax.set_xlabel("Correlation X", color="#444455", fontsize=7.5, labelpad=8)
    ax.set_ylabel("Correlation Y", color="#444455", fontsize=7.5, labelpad=8)
    ax.set_zlabel(args.z_mode, color="#8888aa", fontsize=7.5, labelpad=8)

    n_long = int(is_long.sum())
    n_short = int(is_short.sum())
    title = (
        f"Market Fabric v2  ·  {snap_date.date()}"
        f"   z={args.z_mode}  ·  color={args.color_mode}"
        f"   nodes={len(nodes)}  long={n_long}  short={n_short}"
        f"   lb={args.lookback}d  fw={args.forward_days}d"
        f"   grid={args.grid_size}²  σ={args.smooth_sigma}"
    )
    ax.set_title(title, color="#9999bb", fontsize=8.5, pad=10)

    sm = plt.cm.ScalarMappable(cmap=_CMAP, norm=Normalize(vmin=c_min, vmax=c_max))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.52, pad=0.04, aspect=22)
    cbar.set_label(args.color_mode, color="#8888aa", fontsize=7.5)
    cbar.ax.yaxis.set_tick_params(color="#555566", labelsize=6.5)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="#777788")

    # Legend patch
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=LONG_COLOR, edgecolor="#ffffff", label="Long signal ▼"),
        Patch(facecolor=SHORT_COLOR, edgecolor="#ffffff", label="Short signal ▲"),
        Patch(facecolor=PEER_COLOR, label="Peer anchor"),
    ]
    ax.legend(
        handles=legend_elements,
        loc="upper left",
        fontsize=7,
        facecolor="#111120",
        edgecolor="#333344",
        labelcolor="#aaaacc",
    )

    plt.tight_layout()
    plt.savefig(
        out_path, dpi=args.dpi, facecolor=fig.get_facecolor(), bbox_inches="tight"
    )
    plt.close(fig)
    print(f"  ✓ PNG: {out_path}")


def grid_size_safe(arr, axis=0):
    return arr.shape[axis]


# ═════════════════════════════════════════════════════════════════════════════
# PLOTLY INTERACTIVE RENDER
# ═════════════════════════════════════════════════════════════════════════════


def render_plotly(frame: dict, args: argparse.Namespace, out_path: Path) -> None:
    if not PLOTLY_AVAILABLE:
        print("  [skip] Plotly not available.")
        return

    x, y, z = frame["x"], frame["y"], frame["z"]
    color = frame["color"]
    nodes = frame["nodes"]
    is_long, is_short = frame["is_long"], frame["is_short"]
    confidence = frame["confidence"]
    snap_date = frame["snapshot_date"]
    grid_x, grid_y, grid_z, grid_color = (
        frame["grid_x"],
        frame["grid_y"],
        frame["grid_z"],
        frame["grid_color"],
    )

    traces = []

    # ── Smooth surface ─────────────────────────────────────────────────────
    finite_gc = grid_color[np.isfinite(grid_color)]
    c_min = np.percentile(finite_gc, 2) if len(finite_gc) else -1
    c_max = np.percentile(finite_gc, 98) if len(finite_gc) else 1

    gz_plot = np.where(np.isfinite(grid_z), grid_z, None)
    gc_plot = np.where(np.isfinite(grid_color), grid_color, None)

    surf = go.Surface(
        x=grid_x.tolist(),
        y=grid_y.tolist(),
        z=[[v for v in row] for row in gz_plot],
        surfacecolor=[[v for v in row] for row in gc_plot],
        colorscale="RdYlGn",
        cmin=c_min,
        cmax=c_max,
        opacity=0.72,
        contours=dict(
            z=dict(show=False),
        ),
        lighting=dict(
            ambient=0.5, diffuse=0.8, roughness=0.4, specular=0.5, fresnel=0.2
        ),
        lightposition=dict(x=1, y=1, z=3),
        showscale=True,
        colorbar=dict(
            title=args.color_mode,
            thickness=14,
            len=0.6,
            tickfont=dict(color="#aaaacc"),
            titlefont=dict(color="#aaaacc"),
        ),
        name="Fabric",
    )
    traces.append(surf)

    # ── Nodes ─────────────────────────────────────────────────────────────
    label_set = frame["long_tickers"] | frame["short_tickers"]
    node_hex = [
        LONG_COLOR if is_long[i] else (SHORT_COLOR if is_short[i] else "#555566")
        for i in range(len(nodes))
    ]
    sizes = [
        max(4, 10 + 8 * float(confidence[i])) if (is_long[i] or is_short[i]) else 3
        for i in range(len(nodes))
    ]
    text_labels = [
        (f"▼ {n}" if is_long[i] else f"▲ {n}" if is_short[i] else "")
        for i, n in enumerate(nodes)
    ]
    hover = [
        f"<b>{nodes[i]}</b><br>z: {z[i]:.4f}<br>color: {color[i]:.4f}"
        f"<br>conf: {confidence[i]:.3f}<br>"
        f"{'LONG ▼' if is_long[i] else 'SHORT ▲' if is_short[i] else 'peer'}"
        for i in range(len(nodes))
    ]

    scatter = go.Scatter3d(
        x=x.tolist(),
        y=y.tolist(),
        z=z.tolist(),
        mode="markers+text",
        text=text_labels,
        textposition="top center",
        textfont=dict(size=9, color=node_hex),
        hovertext=hover,
        hoverinfo="text",
        marker=dict(
            size=sizes,
            color=node_hex,
            opacity=0.95,
            line=dict(color="#ffffff", width=0.5),
        ),
        name="Nodes",
    )
    traces.append(scatter)

    layout = go.Layout(
        title=dict(
            text=(
                f"Market Fabric v2  ·  {snap_date.date()}"
                f"  |  z={args.z_mode}  ·  color={args.color_mode}"
            ),
            font=dict(color="#ccccdd", size=13),
        ),
        paper_bgcolor="#080810",
        scene=dict(
            xaxis=dict(
                title="Corr X",
                backgroundcolor="#0a0a16",
                gridcolor="#1a1a2e",
                color="#555566",
            ),
            yaxis=dict(
                title="Corr Y",
                backgroundcolor="#0a0a16",
                gridcolor="#1a1a2e",
                color="#555566",
            ),
            zaxis=dict(
                title=args.z_mode,
                backgroundcolor="#0a0a16",
                gridcolor="#1a1a2e",
                color="#8888aa",
            ),
            camera=dict(eye=dict(x=1.3, y=-1.5, z=0.9)),
            bgcolor="#080810",
            aspectmode="manual",
            aspectratio=dict(x=1, y=1, z=0.6),
        ),
        margin=dict(l=0, r=0, t=45, b=0),
    )

    fig_p = go.Figure(data=traces, layout=layout)
    fig_p.write_html(str(out_path), include_plotlyjs="cdn")
    print(f"  ✓ HTML: {out_path}")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════


def main() -> None:
    args = parse_args()

    print("=== render_market_fabric_v2.py ===")
    print(f"  CuPy GPU:      {'✓' if CUPY_AVAILABLE else '✗ (NumPy fallback)'}")
    print(f"  Scipy:         {'✓' if SCIPY_AVAILABLE else '✗ (quality reduced)'}")
    print(f"  Scipy RBF:     {'✓' if SCIPY_RBF else '✗ (griddata fallback)'}")
    print(f"  Plotly:        {'✓' if PLOTLY_AVAILABLE else '✗ (HTML disabled)'}")
    print(f"  surface_mode:  {args.surface_mode}")
    print(f"  grid_size:     {args.grid_size}²")
    print(f"  smooth_sigma:  {args.smooth_sigma}")
    print(f"  interp_method: {args.interpolation_method}")
    print(f"  extra_nodes:   {args.extra_nodes} ({args.extra_node_mode})")
    print()

    if not CUPY_AVAILABLE:
        warnings.warn("CuPy not found. Using NumPy for correlation/MDS.")

    # ── Load data ──────────────────────────────────────────────────────────
    out_dir = Path(args.out_dir)
    cache_dir = out_dir / "cache"
    frames_dir = out_dir / "frames"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading returns:  {args.returns_meta}")
    returns, meta = load_returns(Path(args.returns_meta))
    all_dates = pd.to_datetime(meta["dates"])
    all_tickers = [str(t).upper() for t in meta["tickers"]]
    ticker_to_idx = {t: i for i, t in enumerate(all_tickers)}
    print(f"  {returns.shape[0]} dates × {returns.shape[1]} tickers")

    print(f"Loading signals:  {args.signals}")
    signals = pd.read_parquet(args.signals)
    signals["date"] = pd.to_datetime(signals["date"])
    signals["ticker"] = signals["ticker"].astype(str).str.upper()
    print(f"  {len(signals)} rows, {signals['date'].nunique()} unique dates")

    short_signals = None
    if args.short_signals:
        print(f"Loading short:    {args.short_signals}")
        short_signals = pd.read_parquet(args.short_signals)
        short_signals["date"] = pd.to_datetime(short_signals["date"])
        short_signals["ticker"] = short_signals["ticker"].astype(str).str.upper()

    # ── Date list ──────────────────────────────────────────────────────────
    if args.animate:
        if not args.start_date or not args.end_date:
            raise ValueError("--animate requires --start-date and --end-date")
        render_dates = list(
            pd.date_range(
                args.start_date, args.end_date, freq=f"{args.frame_step_days}D"
            )
        )
        frames_dir.mkdir(parents=True, exist_ok=True)
        print(
            f"\nAnimation: {len(render_dates)} frames  "
            f"({args.start_date} → {args.end_date}, step={args.frame_step_days}d)"
        )
    else:
        if not args.date:
            raise ValueError("Specify --date or use --animate.")
        render_dates = [pd.Timestamp(args.date)]
        print(f"\nStatic snapshot: {args.date}")

    # ── Global limits (fixed across frames) ───────────────────────────────
    global_z_lim: Optional[tuple] = None
    global_c_lim: Optional[tuple] = None

    prev_frame: Optional[dict] = None
    rendered: list[Path] = []

    for frame_idx, date in enumerate(render_dates):
        print(
            f"\n── Frame {frame_idx + 1}/{len(render_dates)}  requested={date.date()} ──"
        )

        frame = compute_frame(
            date=date,
            returns=returns,
            all_dates=all_dates,
            all_tickers=all_tickers,
            signals=signals,
            short_signals=short_signals,
            ticker_to_idx=ticker_to_idx,
            args=args,
            cache_dir=cache_dir,
            prev_frame=prev_frame,
        )

        if frame is None:
            print(f"  [skip] insufficient data.")
            continue

        print(
            f"  snapshot={frame['snapshot_date'].date()}  "
            f"nodes={len(frame['nodes'])}  "
            f"long={int(frame['is_long'].sum())}  "
            f"short={int(frame['is_short'].sum())}"
        )

        # Temporal smoothing
        if args.temporal_smoothing > 0 and prev_frame is not None:
            frame = apply_temporal_smoothing(frame, prev_frame, args.temporal_smoothing)

        # Fix global limits on first frame
        if (
            args.fixed_limits
            and global_z_lim is None
            and np.isfinite(frame["grid_z"]).any()
        ):
            gz_fin = frame["grid_z"][np.isfinite(frame["grid_z"])]
            gc_fin = frame["grid_color"][np.isfinite(frame["grid_color"])]
            global_z_lim = (
                float(np.percentile(gz_fin, 1)),
                float(np.percentile(gz_fin, 99)),
            )
            global_c_lim = (
                float(np.percentile(gc_fin, 1)),
                float(np.percentile(gc_fin, 99)),
            )

        snap = frame["snapshot_date"]
        safe_date = str(snap.date())
        tag = f"{safe_date}_{args.z_mode}_{args.color_mode}"

        out_png = (
            frames_dir / f"frame_{frame_idx:04d}.png"
            if args.animate
            else out_dir / f"fabric_{tag}.png"
        )

        render_matplotlib(
            frame=frame,
            args=args,
            out_path=out_png,
            z_lim=global_z_lim,
            color_lim=global_c_lim,
            cam_elev=28,
            cam_azim=(-55 if args.fixed_camera else -55),
        )

        if args.interactive and not args.animate:
            render_plotly(frame, args, out_dir / f"interactive_{tag}.html")

        if not args.animate:
            csv_out = out_dir / f"fabric_{tag}_nodes.csv"
            pd.DataFrame(
                {
                    "date": snap,
                    "ticker": frame["nodes"],
                    "is_long": frame["is_long"],
                    "is_short": frame["is_short"],
                    "x": frame["x"],
                    "y": frame["y"],
                    "z": frame["z"],
                    "color": frame["color"],
                    "confidence": frame["confidence"],
                }
            ).to_csv(csv_out, index=False)
            print(f"  ✓ CSV: {csv_out}")

            sig_df = pd.DataFrame(
                {
                    "ticker": frame["nodes"],
                    "is_long": frame["is_long"],
                    "is_short": frame["is_short"],
                    "z": frame["z"],
                    "color": frame["color"],
                    "confidence": frame["confidence"],
                }
            )
            sig_df = sig_df[sig_df["is_long"] | sig_df["is_short"]]
            if len(sig_df):
                print(f"\n  Signal anchors ({len(sig_df)}):")
                print(
                    sig_df.sort_values("confidence", ascending=False)
                    .head(16)
                    .to_string(index=False)
                )

        prev_frame = frame
        rendered.append(out_png)

    print(f"\n{'='*60}")
    print(f"Done. {len(rendered)} frame(s) rendered → {out_dir}")

    if args.animate and rendered:
        print(f"\nTo create MP4 (requires ffmpeg):")
        print(
            f"  ffmpeg -r 8 -i {frames_dir}/frame_%04d.png "
            f"-vcodec libx264 -pix_fmt yuv420p -crf 20 "
            f"{out_dir}/animation_{args.z_mode}_{args.color_mode}.mp4"
        )
        print(f"\nTo create GIF (requires ImageMagick):")
        print(
            f"  convert -delay 12 -loop 0 {frames_dir}/frame_*.png "
            f"{out_dir}/animation_{args.z_mode}_{args.color_mode}.gif"
        )


if __name__ == "__main__":
    main()
