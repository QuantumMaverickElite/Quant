#!/usr/bin/env python3
"""
visualize_market_graph_fabric.py
================================

VisPy playback for graph-first market fabric frames.

Stocks are treated as the fabric:
  stock node         = fabric vertex
  rolling corr edge  = stitching / spring
  node height        = z-mode from frame builder
  node color         = heat metric
  edge brightness    = rolling correlation strength

This visualizer intentionally does no heavy market math while playing.
It reads cached frame .npz files and optional overlay arrays.

Supported overlays:
  - allocator overlay arrays
  - trade / portfolio overlay arrays
  - readable cluster label JSON
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np

from vispy import app, scene
from vispy.io import write_png
from vispy.scene import visuals
from vispy.scene.cameras import TurntableCamera
from vispy.scene.visuals import Text


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Play cached whole-market graph fabric frames.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument("--frames-dir", required=True)
    p.add_argument("--record-root", default="outputs/market_graph_fabric_recordings")
    p.add_argument("--safe-mode", action="store_true")

    p.add_argument(
        "--visual-preset",
        choices=["default", "stress-fabric", "clean-points", "dense-web"],
        default="default",
        help="Convenience preset for visual style.",
    )

    p.add_argument("--ticker-labels", action="store_true")
    p.add_argument("--cluster-labels", action="store_true")
    p.add_argument("--max-cluster-labels", type=int, default=16)
    p.add_argument(
        "--cluster-label-map",
        default=None,
        help="Optional JSON mapping cluster ids to readable cluster labels. "
             "If omitted, frames-dir/cluster_labels.json is used when present.",
    )
    p.add_argument(
        "--max-cluster-label-chars",
        type=int,
        default=42,
        help="Truncate long cluster labels for readability.",
    )

    p.add_argument("--fps", type=int, default=4)
    p.add_argument("--speed", type=int, default=1)
    p.add_argument("--max-labels", type=int, default=10)
    p.add_argument("--node-size", type=float, default=4.0)

    p.add_argument(
        "--use-allocator-overlay",
        action="store_true",
        help="Use allocator overlay arrays inside augmented frames.",
    )
    p.add_argument(
        "--allocator-size-boost",
        type=float,
        default=2.0,
        help="Extra node-size multiplier for allocator overlay scores.",
    )
    p.add_argument(
        "--allocator-highlight-top",
        action="store_true",
        help="Highlight top allocator candidates with special colors.",
    )

    p.add_argument(
        "--use-trade-overlay",
        action="store_true",
        help="Use trade/portfolio overlay arrays inside augmented frames.",
    )
    p.add_argument(
        "--trade-size-boost",
        type=float,
        default=1.8,
        help="Extra size multiplier for active trade nodes.",
    )

    p.add_argument(
        "--node-size-metric",
        choices=["none", "realized_vol_z", "stress", "entropy_z", "confidence"],
        default="realized_vol_z",
        help="Metric used to pulse node size.",
    )

    p.add_argument("--edge-alpha", type=float, default=0.18)
    p.add_argument(
        "--edge-cyan",
        action="store_true",
        help="Render edges in brighter cyan tones for better contrast.",
    )
    p.add_argument("--edge-color-r", type=float, default=0.00)
    p.add_argument("--edge-color-g", type=float, default=0.90)
    p.add_argument("--edge-color-b", type=float, default=1.00)
    p.add_argument("--edge-width", type=float, default=0.65)
    p.add_argument(
        "--edge-color-mode",
        choices=["corr", "delta", "hybrid"],
        default="hybrid",
        help="corr=strength, delta=tightening/loosening, hybrid=strength plus delta tint.",
    )

    p.add_argument("--z-scale", type=float, default=0.18)
    p.add_argument("--hide-edges", action="store_true")
    p.add_argument("--hide-hud", action="store_true")
    p.add_argument("--hide-axes", action="store_true")

    return p.parse_args()


class NavigableCamera(TurntableCamera):
    def on_key_press(self, event):
        key = (event.key.name or "").upper()
        if key in ("A", "LEFT"):
            self.azimuth -= 3.0
        elif key in ("D", "RIGHT"):
            self.azimuth += 3.0
        elif key in ("W", "UP"):
            self.elevation = np.clip(self.elevation + 2.0, -89, 89)
        elif key in ("S", "DOWN"):
            self.elevation = np.clip(self.elevation - 2.0, -89, 89)
        self.view_changed()


PALETTE_T = np.array([0.0, 0.18, 0.34, 0.52, 0.68, 0.82, 1.0], dtype=np.float32)
PALETTE_C = np.array(
    [
        [0.02, 0.01, 0.12],
        [0.05, 0.08, 0.65],
        [0.00, 0.65, 0.95],
        [0.00, 0.95, 0.72],
        [0.95, 0.90, 0.10],
        [1.00, 0.35, 0.00],
        [1.00, 0.08, 0.08],
    ],
    dtype=np.float32,
)

LONG = np.array([0.0, 0.92, 1.0, 1.0], dtype=np.float32)
SHORT = np.array([1.0, 0.16, 0.10, 1.0], dtype=np.float32)


def color_map(values: np.ndarray, vmin: float, vmax: float, alpha: float = 1.0) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    if vmax <= vmin:
        vmax = vmin + 1e-6

    u = np.clip((values - vmin) / (vmax - vmin), 0, 1).ravel()
    out = np.zeros((len(u), 4), dtype=np.float32)

    for i in range(len(PALETTE_T) - 1):
        lo, hi = PALETTE_T[i], PALETTE_T[i + 1]
        mask = (u >= lo) & (u <= hi)
        if not mask.any():
            continue
        s = (u[mask] - lo) / (hi - lo + 1e-9)
        out[mask, :3] = PALETTE_C[i] + s[:, None] * (PALETTE_C[i + 1] - PALETTE_C[i])

    out[:, 3] = alpha
    return out


def load_manifest(root: Path) -> dict:
    path = root / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text())


def frame_path(record: dict, root: Path) -> Path:
    p = Path(record["path"])

    if p.is_absolute() and p.exists():
        return p

    if p.exists():
        return p

    candidate = root / p
    if candidate.exists():
        return candidate

    candidate = root / "frames" / p.name
    if candidate.exists():
        return candidate

    return p


def load_frame(path: Path) -> dict:
    npz = np.load(path, allow_pickle=True)
    return {k: npz[k] for k in npz.files}


def str_array(arr) -> list[str]:
    return [str(x) for x in arr.tolist()]


def scalar_from_frame(frame: dict, key: str, default=np.nan):
    if key not in frame:
        return default
    x = frame[key]
    try:
        arr = np.asarray(x)
        if arr.size == 0:
            return default
        return arr.ravel()[0].item()
    except Exception:
        return default


def fmt_money(x) -> str:
    try:
        if not np.isfinite(float(x)):
            return "n/a"
        return f"${float(x):,.0f}"
    except Exception:
        return "n/a"


def fmt_pct(x) -> str:
    try:
        if not np.isfinite(float(x)):
            return "n/a"
        return f"{float(x):.2%}"
    except Exception:
        return "n/a"


def apply_visual_preset(args: argparse.Namespace) -> argparse.Namespace:
    if args.visual_preset == "stress-fabric":
        args.z_scale = 0.85
        args.edge_alpha = 0.08
        args.edge_width = 0.45
        args.node_size = 5.0
        if getattr(args, "node_size_metric", "none") == "none":
            args.node_size_metric = "realized_vol_z"

    elif args.visual_preset == "clean-points":
        args.z_scale = 0.85
        args.edge_alpha = 0.03
        args.edge_width = 0.25
        args.node_size = 5.5

    elif args.visual_preset == "dense-web":
        args.z_scale = 0.65
        args.edge_alpha = 0.14
        args.edge_width = 0.55
        args.node_size = 4.0

    return args


class MarketGraphFabric:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.root = Path(args.frames_dir)
        self.manifest = load_manifest(self.root)
        self.records = self.manifest["frames"]
        self.limits = self.manifest.get("global_limits", {})
        self.params = self.manifest.get("parameters", {})

        if not self.records:
            raise RuntimeError("No frames in manifest.")

        self.cluster_label_map = self._load_cluster_label_map(args)

        self.idx = 0
        self.speed = max(1, args.speed)
        self.safe_mode = args.safe_mode
        self.fps = min(args.fps, 8) if args.safe_mode else args.fps
        self.playing = True

        self.edges_visible = not args.hide_edges
        self.axes_visible = not args.hide_axes
        self.hud_visible = not args.hide_hud

        self.recording = False
        self.record_root = Path(args.record_root)
        self.record_dir: Path | None = None
        self.record_frames_dir: Path | None = None
        self.record_count = 0

        first = self._load(self.idx)

        self.canvas = scene.SceneCanvas(
            title="Market Graph Fabric",
            keys="interactive",
            bgcolor="#03070c",
            size=(1600, 950),
            show=True,
        )
        self.canvas.events.key_press.connect(self._on_key)
        self.view = self.canvas.central_widget.add_view()

        self._cam_defaults = dict(fov=50, azimuth=34, elevation=24, distance=3.4)
        self.cam = NavigableCamera(**self._cam_defaults)
        self.view.camera = self.cam

        self.edge_lines = visuals.Line(width=args.edge_width)
        self.edge_lines.set_gl_state("translucent", depth_test=True, blend=True)
        self.view.add(self.edge_lines)

        self.nodes = visuals.Markers()
        self.view.add(self.nodes)

        self.long_nodes = visuals.Markers()
        self.view.add(self.long_nodes)

        self.short_nodes = visuals.Markers()
        self.view.add(self.short_nodes)

        self.axis_nodes: list = []
        self.hud_nodes: list[Text] = []
        self.label_nodes: list[Text] = []
        self.cluster_label_nodes: list[Text] = []

        self._create_axes(first)
        self._create_hud()

        if args.ticker_labels:
            max_labels = min(args.max_labels, 12 if self.safe_mode else args.max_labels)
            for _ in range(max_labels):
                t = Text("", color=(0.0, 0.94, 1.0, 1.0), font_size=10, bold=True)
                self.view.add(t)
                self.label_nodes.append(t)

        if args.cluster_labels:
            max_clusters = min(args.max_cluster_labels, 12 if self.safe_mode else args.max_cluster_labels)
            for _ in range(max_clusters):
                t = Text("", color=(1.0, 0.86, 0.18, 0.95), font_size=10, bold=True)
                self.view.add(t)
                self.cluster_label_nodes.append(t)

        self._set_axes_visible(self.axes_visible)
        self._set_hud_visible(self.hud_visible)
        self._update(first)

        self.timer = app.Timer(interval=1.0 / max(1, self.fps))
        self.timer.connect(self._step)
        self.timer.start()

        print("\n" + "─" * 78)
        print(" Market Graph Fabric | stock nodes are the fabric")
        print("─" * 78)
        print(f" frames       : {len(self.records)}")
        print(f" period       : {self.params.get('start_date')} → {self.params.get('end_date')}")
        print(f" max_nodes    : {self.params.get('max_nodes')}")
        print(f" top_k_edges  : {self.params.get('top_k_edges')}")
        print(f" z/color      : {self.params.get('z_mode')} / {self.params.get('color_mode')}")
        print(f" fps/speed    : {self.fps} / {self.speed}")
        print(f" safe mode    : {self.safe_mode}")
        print(
            " controls     : Space pause | +/- speed | E edges | H HUD | T axes | "
            "C clusters | 1/2/3 camera | V record | Q quit"
        )
        print("─" * 78 + "\n")

    def _load_cluster_label_map(self, args: argparse.Namespace) -> dict[str, str]:
        label_map_path = getattr(args, "cluster_label_map", None)

        if label_map_path is None:
            candidate = self.root / "cluster_labels.json"
            if candidate.exists():
                label_map_path = candidate

        if not label_map_path:
            return {}

        try:
            path = Path(label_map_path)
            labels = json.loads(path.read_text())
            labels = {str(k): str(v) for k, v in labels.items()}
            print(f"Loaded cluster labels: {path}")
            return labels
        except Exception as e:
            print(f"WARNING: could not load cluster label map {label_map_path}: {e}")
            return {}

    def _load(self, idx: int) -> dict:
        return load_frame(frame_path(self.records[idx % len(self.records)], self.root))

    def _scaled_positions(self, frame: dict) -> np.ndarray:
        x = frame["x"].astype(np.float32)
        y = frame["y"].astype(np.float32)
        z = frame["z"].astype(np.float32)

        z_min = float(self.limits.get("z_min", np.nanmin(z)))
        z_max = float(self.limits.get("z_max", np.nanmax(z)))

        if z_max <= z_min:
            finite = z[np.isfinite(z)]
            if len(finite) and np.nanmin(finite) < np.nanmax(finite):
                z_min = float(np.nanmin(finite))
                z_max = float(np.nanmax(finite))
            else:
                z_min, z_max = -1.0, 1.0

        z_center = 0.5 * (z_min + z_max)
        z_span = max(1e-6, z_max - z_min)
        z_scaled = (z - z_center) / z_span * self.args.z_scale

        return np.column_stack([x, y, z_scaled]).astype(np.float32)

    def _node_colors(self, frame: dict) -> np.ndarray:
        color = frame["color"].astype(np.float32)
        finite = color[np.isfinite(color)]

        if len(finite):
            cmin = float(self.limits.get("color_min", np.nanpercentile(finite, 1)))
            cmax = float(self.limits.get("color_max", np.nanpercentile(finite, 99)))
        else:
            cmin, cmax = 0.0, 1.0

        return color_map(color, cmin, cmax, alpha=0.82 if self.safe_mode else 0.92)

    def _node_sizes(self, frame: dict) -> np.ndarray:
        base = float(self.args.node_size)
        n = len(frame["x"])

        metric = getattr(self.args, "node_size_metric", "none")
        if metric == "none" or metric not in frame:
            return np.full(n, base, dtype=np.float32)

        vals = np.asarray(frame[metric], dtype=np.float32)
        finite = np.isfinite(vals)

        if finite.sum() < 5:
            return np.full(n, base, dtype=np.float32)

        lo, hi = np.nanpercentile(vals[finite], [5, 98])
        if hi <= lo:
            return np.full(n, base, dtype=np.float32)

        u = np.clip((vals - lo) / (hi - lo), 0.0, 1.0)
        sizes = base * (0.75 + 1.85 * u)

        if self.safe_mode:
            sizes = np.clip(sizes, 2.0, 10.0)
        else:
            sizes = np.clip(sizes, 2.0, 16.0)

        return sizes.astype(np.float32)

    def _apply_allocator_overlay(
        self,
        frame: dict,
        colors: np.ndarray,
        sizes: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        if not getattr(self.args, "use_allocator_overlay", False):
            return colors, sizes

        if "allocator_node_size_score" not in frame:
            return colors, sizes

        out_colors = colors.copy()
        out_sizes = sizes.copy()

        node_size_score = np.asarray(
            frame.get("allocator_node_size_score", np.zeros(len(out_sizes))),
            dtype=np.float32,
        )
        node_alpha_score = np.asarray(
            frame.get("allocator_node_alpha_score", np.zeros(len(out_sizes))),
            dtype=np.float32,
        )

        boost = float(getattr(self.args, "allocator_size_boost", 2.0))
        out_sizes = out_sizes * (1.0 + boost * np.clip(node_size_score, 0.0, 1.0))

        if self.safe_mode:
            out_sizes = np.clip(out_sizes, 2.0, 16.0)
        else:
            out_sizes = np.clip(out_sizes, 2.0, 26.0)

        out_colors[:, 3] = np.maximum(
            out_colors[:, 3],
            np.clip(0.18 + 0.82 * node_alpha_score, 0.18, 1.0),
        )

        if getattr(self.args, "allocator_highlight_top", False):
            top5 = np.asarray(
                frame.get("allocator_is_top_5", np.zeros(len(out_sizes), dtype=bool)),
                dtype=bool,
            )
            top3 = np.asarray(
                frame.get("allocator_is_top_3", np.zeros(len(out_sizes), dtype=bool)),
                dtype=bool,
            )
            top1 = np.asarray(
                frame.get("allocator_is_top_1", np.zeros(len(out_sizes), dtype=bool)),
                dtype=bool,
            )

            out_colors[top5, :3] = np.array([0.30, 0.95, 1.00], dtype=np.float32)
            out_colors[top5, 3] = 1.0

            out_colors[top3, :3] = np.array([1.00, 0.72, 0.18], dtype=np.float32)
            out_colors[top3, 3] = 1.0

            out_colors[top1, :3] = np.array([1.00, 0.96, 0.35], dtype=np.float32)
            out_colors[top1, 3] = 1.0

        return out_colors.astype(np.float32), out_sizes.astype(np.float32)

    def _apply_trade_overlay(
        self,
        frame: dict,
        colors: np.ndarray,
        sizes: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        use_trade = getattr(self.args, "use_trade_overlay", False)

        # Auto-enable if the augmented frame contains trade arrays.
        if not use_trade and "trade_is_active" not in frame:
            return colors, sizes

        if "trade_is_active" not in frame:
            return colors, sizes

        out_colors = colors.copy()
        out_sizes = sizes.copy()

        active = np.asarray(frame.get("trade_is_active", np.zeros(len(out_sizes), dtype=bool)), dtype=bool)
        opened = np.asarray(frame.get("trade_opened_today", np.zeros(len(out_sizes))), dtype=np.float32) > 0
        closed = np.asarray(frame.get("trade_closed_today", np.zeros(len(out_sizes))), dtype=np.float32) > 0
        unreal = np.asarray(frame.get("trade_unrealized_pnl", np.zeros(len(out_sizes))), dtype=np.float32)
        open_ret = np.asarray(frame.get("trade_open_return", np.zeros(len(out_sizes))), dtype=np.float32)

        if active.any():
            pnl_scale = np.nanpercentile(np.abs(unreal[active]), 90) if np.isfinite(unreal[active]).any() else 1.0
            pnl_scale = max(float(pnl_scale), 1.0)
            pnl_strength = np.clip(np.abs(unreal) / pnl_scale, 0.0, 1.0)

            winners = active & (unreal >= 0)
            losers = active & (unreal < 0)

            # Active winners: green/cyan.
            out_colors[winners, :3] = (
                (1.0 - pnl_strength[winners, None]) * out_colors[winners, :3]
                + pnl_strength[winners, None] * np.array([0.15, 1.00, 0.45], dtype=np.float32)
            )

            # Active losers: red/magenta.
            out_colors[losers, :3] = (
                (1.0 - pnl_strength[losers, None]) * out_colors[losers, :3]
                + pnl_strength[losers, None] * np.array([1.00, 0.12, 0.25], dtype=np.float32)
            )

            out_colors[active, 3] = 1.0

            boost = float(getattr(self.args, "trade_size_boost", 1.8))
            ret_boost = np.clip(np.abs(open_ret), 0.0, 1.0)
            out_sizes[active] = out_sizes[active] * (1.0 + boost * (0.55 + 0.45 * ret_boost[active]))

        # Opened today: white.
        if opened.any():
            out_colors[opened, :3] = np.array([1.0, 1.0, 1.0], dtype=np.float32)
            out_colors[opened, 3] = 1.0
            out_sizes[opened] = out_sizes[opened] * 1.5

        # Closed today: yellow/orange.
        if closed.any():
            out_colors[closed, :3] = np.array([1.0, 0.82, 0.10], dtype=np.float32)
            out_colors[closed, 3] = 1.0
            out_sizes[closed] = out_sizes[closed] * 1.4

        if self.safe_mode:
            out_sizes = np.clip(out_sizes, 2.0, 18.0)
        else:
            out_sizes = np.clip(out_sizes, 2.0, 30.0)

        return out_colors.astype(np.float32), out_sizes.astype(np.float32)

    def _recolor_edges_for_visibility(self, edge_colors: np.ndarray) -> np.ndarray:
        if edge_colors is None or len(edge_colors) == 0:
            return edge_colors

        out = np.asarray(edge_colors, dtype=np.float32).copy()

        if getattr(self.args, "edge_cyan", False):
            r, g, b = 0.00, 0.95, 1.00
        else:
            r = float(getattr(self.args, "edge_color_r", 0.00))
            g = float(getattr(self.args, "edge_color_g", 0.90))
            b = float(getattr(self.args, "edge_color_b", 1.00))

        out[:, 0] = r
        out[:, 1] = g
        out[:, 2] = b
        out[:, 3] = np.clip(np.maximum(out[:, 3], float(self.args.edge_alpha)), 0.0, 1.0)

        return out.astype(np.float32)

    def _edge_data(self, frame: dict, pos: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        src = frame["edge_src"].astype(np.int64)
        dst = frame["edge_dst"].astype(np.int64)
        corr = frame["edge_corr"].astype(np.float32)

        if len(src) == 0:
            return np.zeros((0, 3), np.float32), np.zeros((0, 4), np.float32)

        seg = np.empty((len(src) * 2, 3), dtype=np.float32)
        seg[0::2] = pos[src]
        seg[1::2] = pos[dst]

        min_corr = float(self.params.get("min_edge_corr", 0.35))
        strength = np.clip((corr - min_corr) / (1.0 - min_corr + 1e-6), 0.0, 1.0)

        alpha = min(self.args.edge_alpha, 0.12 if self.safe_mode else self.args.edge_alpha)
        mode = getattr(self.args, "edge_color_mode", "hybrid")

        corr_rgb = np.column_stack(
            [
                0.06 + 0.20 * strength,
                0.35 + 0.55 * strength,
                0.70 + 0.30 * strength,
            ]
        ).astype(np.float32)

        if "edge_corr_delta" in frame:
            delta = frame["edge_corr_delta"].astype(np.float32)
        else:
            delta = np.zeros_like(corr, dtype=np.float32)

        finite = np.isfinite(delta)
        if finite.sum() >= 5:
            lo, hi = np.nanpercentile(delta[finite], [2, 98])
            scale = max(abs(float(lo)), abs(float(hi)), 1e-6)
            d = np.clip(delta / scale, -1.0, 1.0)
        else:
            d = np.zeros_like(delta, dtype=np.float32)

        tighten = np.clip(d, 0.0, 1.0)
        loosen = np.clip(-d, 0.0, 1.0)

        delta_rgb = np.zeros((len(corr), 3), dtype=np.float32)
        delta_rgb[:, 0] = 0.08 + 0.92 * tighten + 0.15 * loosen
        delta_rgb[:, 1] = 0.28 + 0.42 * tighten + 0.05 * loosen
        delta_rgb[:, 2] = 0.75 - 0.55 * tighten + 0.25 * loosen

        if mode == "corr":
            rgb = corr_rgb
        elif mode == "delta":
            rgb = delta_rgb
        else:
            mix = np.clip(np.abs(d), 0.0, 1.0)[:, None]
            rgb = (1.0 - 0.65 * mix) * corr_rgb + (0.65 * mix) * delta_rgb

        edge_col = np.zeros((len(src) * 2, 4), dtype=np.float32)
        edge_col[0::2, :3] = rgb
        edge_col[1::2, :3] = rgb

        dynamic_alpha = alpha * (0.55 + 0.75 * np.clip(np.abs(d), 0.0, 1.0))
        edge_col[0::2, 3] = dynamic_alpha
        edge_col[1::2, 3] = dynamic_alpha

        return seg, edge_col

    def _update(self, frame: dict | None = None) -> None:
        if frame is None:
            frame = self._load(self.idx)

        pos = self._scaled_positions(frame)
        colors = self._node_colors(frame)
        sizes = self._node_sizes(frame)

        colors, sizes = self._apply_allocator_overlay(frame, colors, sizes)
        colors, sizes = self._apply_trade_overlay(frame, colors, sizes)

        is_long = frame["is_long"].astype(bool)
        is_short = frame["is_short"].astype(bool)
        peer = ~(is_long | is_short)

        if self.edges_visible:
            seg, edge_col = self._edge_data(frame, pos)
            edge_col = self._recolor_edges_for_visibility(edge_col)
            self.edge_lines.set_data(seg, color=edge_col, connect="segments")
        else:
            self.edge_lines.set_data(
                np.zeros((0, 3), np.float32),
                color=(0, 0, 0, 0),
                connect="segments",
            )

        self.nodes.set_data(
            pos[peer],
            face_color=colors[peer] if peer.any() else np.zeros((0, 4), np.float32),
            edge_color=(0.02, 0.05, 0.10, 0.1),
            size=sizes[peer] if peer.any() else 1.0,
        )

        self.long_nodes.set_data(
            pos[is_long] if is_long.any() else np.zeros((0, 3), np.float32),
            face_color=colors[is_long] if is_long.any() else tuple(LONG),
            edge_color=(1, 1, 1, 0.95),
            size=(sizes[is_long] + (5 if self.safe_mode else 7)) if is_long.any() else 1.0,
        )

        self.short_nodes.set_data(
            pos[is_short] if is_short.any() else np.zeros((0, 3), np.float32),
            face_color=colors[is_short] if is_short.any() else tuple(SHORT),
            edge_color=(1, 1, 1, 0.95),
            size=(sizes[is_short] + (5 if self.safe_mode else 7)) if is_short.any() else 1.0,
        )

        self._update_labels(frame, pos)
        self._update_cluster_labels(frame, pos)
        self._update_hud(frame)

    def _create_axes(self, frame: dict) -> None:
        x_min = float(self.limits.get("x_min", np.nanmin(frame["x"])))
        x_max = float(self.limits.get("x_max", np.nanmax(frame["x"])))
        y_min = float(self.limits.get("y_min", np.nanmin(frame["y"])))
        y_max = float(self.limits.get("y_max", np.nanmax(frame["y"])))

        z0 = -0.18
        x0 = x_min - 0.06 * (x_max - x_min)
        y0 = y_min - 0.06 * (y_max - y_min)

        def line(points, color, width=1.4):
            l = visuals.Line(width=width)
            l.set_data(np.array(points, dtype=np.float32), color=color)
            self.view.add(l)
            self.axis_nodes.append(l)

        def text(label, pos, color, size=9, bold=False):
            t = Text(label, pos=pos, color=color, font_size=size, bold=bold, anchor_x="center")
            self.view.add(t)
            self.axis_nodes.append(t)

        line([[x0, y0, z0], [x_max, y0, z0]], (0, 0.9, 1, 0.65), 1.5)
        line([[x0, y0, z0], [x0, y_max, z0]], (0.75, 0.45, 1, 0.65), 1.5)
        line([[x0, y0, z0], [x0, y0, 0.20]], (1, 0.78, 0.10, 0.7), 1.5)

        text("Correlation X", (x_max, y0, z0), (0, 0.9, 1, 0.9), 10, True)
        text("Correlation Y", (x0, y_max, z0), (0.75, 0.45, 1, 0.9), 10, True)
        text(f"Z: {self.params.get('z_mode')}", (x0, y0, 0.22), (1, 0.78, 0.1, 0.9), 10, True)

    def _set_axes_visible(self, visible: bool) -> None:
        self.axes_visible = visible
        for n in self.axis_nodes:
            n.visible = visible

    def _create_hud(self) -> None:
        x0, y0, z0 = 0.66, 0.49, 0.24
        for i in range(19):
            color = (0.80, 0.90, 1.0, 0.90)
            size = 8
            bold = False

            if i == 0:
                color = (0, 0.95, 1, 1)
                size = 14
                bold = True

            t = Text(
                "",
                pos=(x0, y0, z0 - i * 0.041),
                color=color,
                font_size=size,
                bold=bold,
                anchor_x="left",
            )
            self.view.add(t)
            self.hud_nodes.append(t)

    def _set_hud_visible(self, visible: bool) -> None:
        self.hud_visible = visible
        for n in self.hud_nodes:
            n.visible = visible

    def _short_cluster_label(self, label: str) -> str:
        max_chars = int(getattr(self.args, "max_cluster_label_chars", 42))
        if max_chars <= 0 or len(label) <= max_chars:
            return label
        return label[: max_chars - 1] + "…"

    def _update_cluster_labels(self, frame: dict, pos: np.ndarray) -> None:
        if not self.cluster_label_nodes:
            return

        if "cluster_id" not in frame:
            for node in self.cluster_label_nodes:
                node.text = ""
            return

        cluster_id = np.asarray(frame["cluster_id"], dtype=np.int32)
        valid = cluster_id >= 0

        if not valid.any():
            for node in self.cluster_label_nodes:
                node.text = ""
            return

        z_lift = 0.055
        clusters = []

        for cid in sorted(np.unique(cluster_id[valid]).tolist()):
            mask = cluster_id == cid
            count = int(mask.sum())
            if count < 5:
                continue

            center = np.nanmean(pos[mask], axis=0)
            top_z = float(np.nanpercentile(pos[mask, 2], 90))
            center[2] = top_z + z_lift
            clusters.append((count, int(cid), center))

        clusters.sort(reverse=True, key=lambda x: x[0])

        for k, node in enumerate(self.cluster_label_nodes):
            if k >= len(clusters):
                node.text = ""
                continue

            count, cid, center = clusters[k]
            base_label = self.cluster_label_map.get(str(cid), f"C{cid}")
            base_label = self._short_cluster_label(base_label)

            node.text = f"{base_label} ({count})"
            node.pos = tuple(center.astype(np.float32))
            node.color = (1.0, 0.86, 0.18, 0.95)

    def _update_hud(self, frame: dict) -> None:
        tickers = str_array(frame["tickers"])
        is_long = frame["is_long"].astype(bool)
        is_short = frame["is_short"].astype(bool)
        conf = frame["confidence"].astype(np.float32) if "confidence" in frame else np.zeros(len(tickers), dtype=np.float32)

        def top(mask, n=5):
            idx = np.where(mask)[0]
            if len(idx) == 0:
                return "none"
            idx = idx[np.argsort(conf[idx])[::-1]][:n]
            return ", ".join([tickers[i] for i in idx])

        ctx = {}
        try:
            ctx = json.loads(str(frame.get("ctx_json", "{}")))
        except Exception:
            pass

        date = str(frame["date"])

        trade_overlay_on = "trade_is_active" in frame
        allocator_overlay_on = getattr(self.args, "use_allocator_overlay", False) and (
            "allocator_final_signal_score" in frame or "allocator_node_size_score" in frame
        )

        equity = scalar_from_frame(frame, "portfolio_equity", np.nan)
        drawdown = scalar_from_frame(frame, "portfolio_drawdown", np.nan)
        open_trades = scalar_from_frame(frame, "portfolio_open_trades", 0)
        active_tickers = scalar_from_frame(frame, "portfolio_active_tickers", 0)
        unrealized = scalar_from_frame(frame, "portfolio_unrealized_pnl", np.nan)
        realized_today = scalar_from_frame(frame, "portfolio_realized_pnl_today", np.nan)
        realized_cum = scalar_from_frame(frame, "portfolio_realized_pnl_cum", np.nan)

        lines = [
            "MARKET GRAPH FABRIC",
            f"{'PLAY' if self.playing else 'PAUSE'} | speed={self.speed} | edges={'on' if self.edges_visible else 'off'} | edge={getattr(self.args, 'edge_color_mode', 'hybrid')} | rec={'on' if self.recording else 'off'}",
            f"Date       : {date}     Frame {self.idx + 1}/{len(self.records)}",
            "Fabric     : stocks = vertices, correlations = stitching",
            f"Z / color  : {self.params.get('z_mode')} / {self.params.get('color_mode')}",
            f"Node size  : {getattr(self.args, 'node_size_metric', 'none')}",
            f"Nodes      : {len(tickers)} | Edges: {len(frame['edge_src'])}",
            f"Allocator  : {'on' if allocator_overlay_on else 'off'}",
            f"Trades     : {'on' if trade_overlay_on else 'off'} | open={int(open_trades)} | active tickers={int(active_tickers)}",
            f"Equity     : {fmt_money(equity)} | DD={fmt_pct(drawdown)}",
            f"PnL        : unreal={fmt_money(unrealized)} | realized today={fmt_money(realized_today)} | realized cum={fmt_money(realized_cum)}",
            f"Regime     : {ctx.get('regime', 'UNKNOWN')}",
            f"Longs      : {top(is_long)}",
            f"Shorts     : {top(is_short)}",
            "Colors     : cyan/orange=signals | green/red=active trade PnL",
            "Clusters   : C toggles labels | JSON labels auto-load if present",
            "Controls   : Space pause | E edges | H HUD | T axes",
            "Cameras    : 1 default | 2 top | 3 side | +/- speed",
            "Record     : V start/stop | Q quit",
        ]

        for node, line in zip(self.hud_nodes, lines):
            node.text = line

    def _update_labels(self, frame: dict, pos: np.ndarray) -> None:
        if not self.label_nodes:
            return

        tickers = np.array([str(t) for t in frame["tickers"].tolist()])
        conf = frame["confidence"].astype(np.float32) if "confidence" in frame else np.zeros(len(tickers), dtype=np.float32)

        is_long = frame["is_long"].astype(bool)
        is_short = frame["is_short"].astype(bool)

        trade_active = np.asarray(
            frame.get("trade_is_active", np.zeros(len(tickers), dtype=bool)),
            dtype=bool,
        )
        trade_pnl = np.asarray(
            frame.get("trade_unrealized_pnl", np.zeros(len(tickers), dtype=np.float32)),
            dtype=np.float32,
        )

        active_idx = np.where(trade_active)[0]
        if len(active_idx):
            active_idx = active_idx[np.argsort(np.abs(trade_pnl[active_idx]))[::-1]]

        long_idx = np.where(is_long)[0]
        short_idx = np.where(is_short)[0]

        if len(long_idx):
            long_idx = long_idx[np.argsort(conf[long_idx])[::-1]]
        if len(short_idx):
            short_idx = short_idx[np.argsort(conf[short_idx])[::-1]]

        max_total = len(self.label_nodes)
        half = max(1, max_total // 2)

        order: list[tuple[int, str]] = []

        # Label active trades first because they explain portfolio compounding.
        for i in active_idx[: max(1, max_total // 3)]:
            order.append((int(i), "T"))

        used = {i for i, _side in order}

        for i in long_idx[:half]:
            if int(i) not in used and len(order) < max_total:
                order.append((int(i), "L"))
                used.add(int(i))

        for i in short_idx[:half]:
            if int(i) not in used and len(order) < max_total:
                order.append((int(i), "S"))
                used.add(int(i))

        both = np.concatenate([long_idx, short_idx]) if len(long_idx) or len(short_idx) else np.array([], dtype=int)
        remaining = np.array([int(i) for i in both if int(i) not in used], dtype=int)

        if len(remaining):
            remaining = remaining[np.argsort(conf[remaining])[::-1]]
            for i in remaining:
                if len(order) >= max_total:
                    break
                order.append((int(i), "L" if is_long[int(i)] else "S"))

        z_span = float(np.nanmax(pos[:, 2]) - np.nanmin(pos[:, 2])) if np.isfinite(pos[:, 2]).any() else 1.0
        dz = max(0.025, 0.045 * z_span)

        for k, node in enumerate(self.label_nodes):
            if k >= len(order):
                node.text = ""
                continue

            i, side = order[k]

            if side == "T":
                node.text = f"T:{tickers[i]}"
            else:
                node.text = f"{side}:{tickers[i]}"

            node.pos = (float(pos[i, 0]), float(pos[i, 1]), float(pos[i, 2] + dz))

            if side == "T":
                if trade_pnl[i] >= 0:
                    node.color = (0.20, 1.00, 0.48, 1.0)
                else:
                    node.color = (1.00, 0.14, 0.24, 1.0)
            elif side == "L":
                node.color = (0.0, 0.94, 1.0, 1.0)
            else:
                node.color = (1.0, 0.18, 0.95, 1.0)

    def _step(self, event) -> None:
        if not self.playing:
            return

        self.idx = (self.idx + self.speed) % len(self.records)
        self._update(self._load(self.idx))

        if self.recording:
            self._record_frame()

        self.canvas.update()

    def _save_canvas_png(self, path: Path) -> None:
        self.canvas.update()
        img = self.canvas.render(alpha=False)
        write_png(str(path), img)

    def _start_recording(self) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.record_dir = self.record_root / f"{self.root.name}_{ts}"
        self.record_frames_dir = self.record_dir / "frames"
        self.record_frames_dir.mkdir(parents=True, exist_ok=True)
        self.record_count = 0
        self.recording = True
        print(f"[record] started -> {self.record_dir}")

    def _stop_recording(self) -> None:
        self.recording = False
        print(f"[record] stopped frames={self.record_count}")
        if self.record_frames_dir and self.record_dir:
            print("manual ffmpeg:")
            print(
                f"  ffmpeg -framerate {self.fps} "
                f"-i {self.record_frames_dir}/frame_%05d.png "
                f"-pix_fmt yuv420p {self.record_dir}/playback.mp4"
            )

    def _record_frame(self) -> None:
        if self.record_frames_dir is None:
            return

        self._save_canvas_png(self.record_frames_dir / f"frame_{self.record_count:05d}.png")
        self.record_count += 1

    def _toggle_recording(self) -> None:
        self._stop_recording() if self.recording else self._start_recording()

    def _on_key(self, event) -> None:
        key = (event.key.name or "").upper()

        if key in ("W", "A", "S", "D", "UP", "DOWN", "LEFT", "RIGHT"):
            self.cam.on_key_press(event)
            return

        if key in ("R", "0"):
            self.cam.set_state(self._cam_defaults)
            self.canvas.update()

        elif key == "SPACE":
            self.playing = not self.playing
            self._update()
            self.canvas.update()

        elif key in ("+", "=", "PLUS", "]"):
            self.speed += 1
            self._update()
            self.canvas.update()

        elif key in ("-", "_", "MINUS", "["):
            self.speed = max(1, self.speed - 1)
            self._update()
            self.canvas.update()

        elif key == "E":
            self.edges_visible = not self.edges_visible
            self._update()
            self.canvas.update()

        elif key == "H":
            self._set_hud_visible(not self.hud_visible)
            self.canvas.update()

        elif key == "C":
            for node in self.cluster_label_nodes:
                node.visible = not node.visible
            self.canvas.update()

        elif key == "T":
            self._set_axes_visible(not self.axes_visible)
            self.canvas.update()

        elif key == "1":
            self.cam.azimuth = 34
            self.cam.elevation = 24
            self.cam.distance = 3.4
            self.canvas.update()

        elif key == "2":
            self.cam.azimuth = 0
            self.cam.elevation = 89
            self.cam.distance = 3.4
            self.canvas.update()

        elif key == "3":
            self.cam.azimuth = 90
            self.cam.elevation = 5
            self.cam.distance = 3.4
            self.canvas.update()

        elif key == "V":
            self._toggle_recording()
            self._update()
            self.canvas.update()

        elif key == "S" and "Shift" in [m.name for m in (event.modifiers or [])]:
            filename = Path(f"market_graph_fabric_{datetime.now():%Y%m%d_%H%M%S}.png")
            self._save_canvas_png(filename)
            print(f"[screenshot] -> {filename}")

        elif key in ("Q", "ESCAPE"):
            if self.recording:
                self._stop_recording()
            self.canvas.close()
            app.quit()


_VIZ = None


def main() -> None:
    global _VIZ
    args = parse_args()
    args = apply_visual_preset(args)
    _VIZ = MarketGraphFabric(args)
    app.run()


if __name__ == "__main__":
    main()
