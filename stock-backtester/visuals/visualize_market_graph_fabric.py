#!/usr/bin/env python3
"""
visualize_market_graph_fabric.py
================================

VisPy playback for graph-first market fabric frames.

This version treats stocks as the fabric:
  stock node       = fabric vertex
  rolling corr edge = stitching / spring
  node height      = z-mode from frame builder
  node color       = heat metric
  edge brightness  = rolling correlation strength

It intentionally does no heavy market math while playing.
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
    p.add_argument("--fps", type=int, default=4)
    p.add_argument("--speed", type=int, default=1)
    p.add_argument("--max-labels", type=int, default=10)
    p.add_argument("--node-size", type=float, default=4.0)
    p.add_argument(
        "--node-size-metric",
        choices=["none", "realized_vol_z", "stress", "entropy_z", "confidence"],
        default="realized_vol_z",
        help="Metric used to pulse node size.",
    )
    p.add_argument("--edge-alpha", type=float, default=0.18)
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
PEER = np.array([0.42, 0.48, 0.62, 0.72], dtype=np.float32)


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
    return p


def load_frame(path: Path) -> dict:
    npz = np.load(path, allow_pickle=True)
    return {k: npz[k] for k in npz.files}


def str_array(arr) -> list[str]:
    return [str(x) for x in arr.tolist()]



def apply_visual_preset(args: argparse.Namespace) -> argparse.Namespace:
    """
    Apply lightweight visual presets.

    stress-fabric:
        Best current default. Keeps the correlation stitching visible without
        letting it dominate the stock nodes.

    clean-points:
        Mostly node heat, minimal fabric stitching.

    dense-web:
        Stronger correlation web for inspecting market tightening.
    """
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
                t = Text("", color=(1.0, 0.86, 0.18, 0.95), font_size=11, bold=True)
                self.view.add(t)
                self.cluster_label_nodes.append(t)

        # CLUSTER_LABEL_PATCH_DONE
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
        print(" controls     : Space pause | +/- speed | E edges | H HUD | T axes | C clusters | 1/2/3 camera | V record | Q quit")
        print("─" * 78 + "\n")

    def _load(self, idx: int) -> dict:
        return load_frame(frame_path(self.records[idx % len(self.records)], Path.cwd()))

    def _scaled_positions(self, frame: dict) -> np.ndarray:
        x = frame["x"].astype(np.float32)
        y = frame["y"].astype(np.float32)
        z = frame["z"].astype(np.float32)

        z_min = float(self.limits.get("z_min", np.nanmin(z)))
        z_max = float(self.limits.get("z_max", np.nanmax(z)))
        if z_max <= z_min:
            # Sparse peer_spread_z often has 995 zeros and only 5 signal valleys.
            finite = z[np.isfinite(z)]
            if len(finite) and np.nanmin(finite) < np.nanmax(finite):
                z_min = float(np.nanmin(finite))
                z_max = float(np.nanmax(finite))
            else:
                z_min, z_max = -1.0, 1.0

        z_center = 0.5 * (z_min + z_max)
        z_span = max(1e-6, z_max - z_min)
        z_scaled = (z - z_center) / z_span * self.args.z_scale

        pos = np.column_stack([x, y, z_scaled]).astype(np.float32)
        return pos

    def _node_colors(self, frame: dict) -> np.ndarray:
        color = frame["color"].astype(np.float32)
        cmin = float(self.limits.get("color_min", np.nanpercentile(color[np.isfinite(color)], 1)))
        cmax = float(self.limits.get("color_max", np.nanpercentile(color[np.isfinite(color)], 99)))
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

        # Default: blue/cyan edges by correlation strength.
        corr_rgb = np.column_stack([
            0.06 + 0.20 * strength,
            0.35 + 0.55 * strength,
            0.70 + 0.30 * strength,
        ]).astype(np.float32)

        if "edge_corr_delta" in frame:
            delta = frame["edge_corr_delta"].astype(np.float32)
        else:
            delta = np.zeros_like(corr, dtype=np.float32)

        finite = np.isfinite(delta)
        if finite.sum() >= 5:
            lo, hi = np.nanpercentile(delta[finite], [2, 98])
            scale = max(abs(lo), abs(hi), 1e-6)
            d = np.clip(delta / scale, -1.0, 1.0)
        else:
            d = np.zeros_like(delta, dtype=np.float32)

        # delta coloring:
        #   positive = fabric tightening, warm orange/red
        #   negative = fabric loosening, blue/violet
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
            # Hybrid: mostly correlation strength, but tinted by tension.
            mix = np.clip(np.abs(d), 0.0, 1.0)[:, None]
            rgb = (1.0 - 0.65 * mix) * corr_rgb + (0.65 * mix) * delta_rgb

        edge_col = np.zeros((len(src) * 2, 4), dtype=np.float32)
        edge_col[0::2, :3] = rgb
        edge_col[1::2, :3] = rgb

        # Make changing edges slightly more visible.
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

        is_long = frame["is_long"].astype(bool)
        is_short = frame["is_short"].astype(bool)
        peer = ~(is_long | is_short)

        if self.edges_visible:
            seg, edge_col = self._edge_data(frame, pos)
            self.edge_lines.set_data(seg, color=edge_col, connect="segments")
        else:
            self.edge_lines.set_data(np.zeros((0, 3), np.float32), color=(0, 0, 0, 0), connect="segments")

        self.nodes.set_data(
            pos[peer],
            face_color=colors[peer] if peer.any() else np.zeros((0, 4), np.float32),
            edge_color=(0.02, 0.05, 0.10, 0.1),
            size=sizes[peer] if peer.any() else 1.0,
        )

        self.long_nodes.set_data(
            pos[is_long] if is_long.any() else np.zeros((0, 3), np.float32),
            face_color=tuple(LONG),
            edge_color=(1, 1, 1, 0.95),
            size=(sizes[is_long] + (5 if self.safe_mode else 7)) if is_long.any() else 1.0,
        )

        self.short_nodes.set_data(
            pos[is_short] if is_short.any() else np.zeros((0, 3), np.float32),
            face_color=tuple(SHORT),
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
        x0, y0, z0 = 0.68, 0.46, 0.22
        for i in range(13):
            color = (0.80, 0.90, 1.0, 0.90)
            size = 9
            bold = False
            if i == 0:
                color = (0, 0.95, 1, 1)
                size = 14
                bold = True
            t = Text("", pos=(x0, y0, z0 - i * 0.045), color=color, font_size=size, bold=bold, anchor_x="left")
            self.view.add(t)
            self.hud_nodes.append(t)

    def _set_hud_visible(self, visible: bool) -> None:
        self.hud_visible = visible
        for n in self.hud_nodes:
            n.visible = visible

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
            # Use top z node to lift label above the cluster.
            top_z = float(np.nanpercentile(pos[mask, 2], 90))
            center[2] = top_z + z_lift
            clusters.append((count, int(cid), center))

        clusters.sort(reverse=True, key=lambda x: x[0])

        for k, node in enumerate(self.cluster_label_nodes):
            if k >= len(clusters):
                node.text = ""
                continue

            count, cid, center = clusters[k]
            node.text = f"C{cid} ({count})"
            node.pos = tuple(center.astype(np.float32))
            node.color = (1.0, 0.86, 0.18, 0.95)

    def _update_hud(self, frame: dict) -> None:
        tickers = str_array(frame["tickers"])
        is_long = frame["is_long"].astype(bool)
        is_short = frame["is_short"].astype(bool)
        conf = frame["confidence"].astype(np.float32)

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
        lines = [
            "MARKET GRAPH FABRIC",
            f"{'PLAY' if self.playing else 'PAUSE'} | speed={self.speed} | edges={'on' if self.edges_visible else 'off'} | edge={getattr(self.args, 'edge_color_mode', 'hybrid')} | rec={'on' if self.recording else 'off'}",
            f"Date       : {date}     Frame {self.idx + 1}/{len(self.records)}",
            "Fabric     : stocks = vertices, correlations = stitching",
            "X/Y        : rolling correlation geometry",
            f"Z height   : {self.params.get('z_mode')}",
            f"Heat/color : {self.params.get('color_mode')}",
            f"Node size  : {getattr(self.args, 'node_size_metric', 'none')}",
            f"Nodes      : {len(tickers)} | Edges: {len(frame['edge_src'])}",
            f"Regime     : {ctx.get('regime', 'UNKNOWN')}",
            f"Longs      : {top(is_long)}",
            f"Shorts     : {top(is_short)}",
            "Controls   : Space pause | E edges | H HUD | T axes",
            "Cameras    : 1 default | 2 top | 3 side | +/- speed",
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

        long_idx = np.where(is_long)[0]
        short_idx = np.where(is_short)[0]

        if len(long_idx):
            long_idx = long_idx[np.argsort(conf[long_idx])[::-1]]
        if len(short_idx):
            short_idx = short_idx[np.argsort(conf[short_idx])[::-1]]

        # Balanced long/short display:
        # In combined mode, do not let one side consume all label slots.
        max_total = len(self.label_nodes)
        half = max(1, max_total // 2)

        order: list[tuple[int, str]] = []
        order.extend([(int(i), "L") for i in long_idx[:half]])
        order.extend([(int(i), "S") for i in short_idx[:half]])

        # Fill any leftover slots with strongest remaining signals.
        used = {i for i, _side in order}
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
            node.text = f"{side}:{tickers[i]}"
            node.pos = (float(pos[i, 0]), float(pos[i, 1]), float(pos[i, 2] + dz))

            if side == "L":
                node.color = (0.0, 0.94, 1.0, 1.0)
            else:
                # Magenta makes shorts visible against orange/red entropy heat.
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
        if self.record_frames_dir:
            print("manual ffmpeg:")
            print(f"  ffmpeg -framerate {self.fps} -i {self.record_frames_dir}/frame_%05d.png -pix_fmt yuv420p {self.record_dir}/playback.mp4")

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
