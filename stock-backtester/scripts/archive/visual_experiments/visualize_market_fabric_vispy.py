"""
visualize_market_fabric_vispy.py
================================
Lightweight VisPy playback for precomputed Market Fabric frames.

This script intentionally does NO heavy market math in the animation loop:
  - no rolling correlations
  - no MDS
  - no interpolation
  - no gaussian smoothing

It loads cached .npz frames created by scripts/build_market_fabric_frames.py,
creates one reusable Mesh visual, and updates GPU buffers each frame.

Controls:
  LMB drag          : orbit
  RMB drag          : pan
  Scroll            : zoom
  W/S or Up/Down    : tilt elevation
  A/D or Left/Right : rotate azimuth
  R                 : reset camera
  Space             : pause / play
  + / =             : increase speed
  - / _             : decrease speed
  V                 : start / stop recording frames
  Shift+S           : screenshot
  Q / Esc           : quit

Example:
  python scripts/visualize_market_fabric_vispy.py \
    --frames-dir outputs/reports/plots/market_fabric_vispy_2020 \
    --ticker-labels \
    --safe-mode
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
from vispy.scene.visuals import Line, Text


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--frames-dir", required=True, help="Directory containing manifest.json and frames/")
    p.add_argument("--record-root", default="outputs/market_fabric_recordings")
    p.add_argument("--ticker-labels", action="store_true")
    p.add_argument("--safe-mode", action="store_true", help="Lower alpha/FPS/labels for laptop stability.")
    p.add_argument("--fps", type=int, default=5)
    p.add_argument("--speed", type=int, default=1, help="Frames advanced per timer tick.")
    p.add_argument("--max-labels", type=int, default=8)
    p.add_argument("--alpha", type=float, default=0.88)
    p.add_argument("--node-alpha", type=float, default=0.80)
    p.add_argument("--wire-grid", action="store_true", help="Add lightweight reference grid.")
    p.add_argument("--hide-axes", action="store_true", help="Start with axis/tick/colorbar helpers hidden.")
    p.add_argument("--hide-hud", action="store_true", help="Start with HUD hidden.")
    return p.parse_args()


class NavigableCamera(TurntableCamera):
    def viewbox_mouse_event(self, event):
        if event.handled or not self.interactive:
            return
        if event.type == "mouse_move" and 2 in event.buttons:
            p1 = event.mouse_event.press_event.pos
            p2 = event.mouse_event.pos
            norm = np.mean(self._viewbox.size)
            if self._event_value is None or len(self._event_value) == 2:
                self._event_value = self.center
            dist = (p1 - p2) / norm * self._scale_factor
            dist[1] *= -1
            dx, dy, dz = self._dist_to_trans(dist)
            ff = self._flip_factors
            up, forward, right = self._get_dim_vectors()
            dx, dy, dz = right * dx + forward * dy + up * dz
            dx, dy, dz = ff[0] * dx, ff[1] * dy, dz * ff[2]
            c = self._event_value
            self.center = c[0] + dx, c[1] + dy, c[2] + dz
            event.handled = True
            return
        super().viewbox_mouse_event(event)

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


_PT = np.array([0.00, 0.12, 0.28, 0.44, 0.58, 0.70, 0.82, 0.93, 1.00], dtype=np.float32)
_PC = np.array([
    [0.02, 0.01, 0.14],
    [0.14, 0.03, 0.60],
    [0.00, 0.42, 0.92],
    [0.00, 0.82, 0.82],
    [0.12, 0.88, 0.25],
    [0.96, 0.84, 0.00],
    [1.00, 0.38, 0.00],
    [1.00, 0.08, 0.08],
    [1.00, 0.96, 0.96],
], dtype=np.float32)
LONG_RGBA = np.array([0.00, 0.90, 1.00, 1.00], dtype=np.float32)
SHORT_RGBA = np.array([1.00, 0.18, 0.12, 1.00], dtype=np.float32)
PEER_RGBA = np.array([0.45, 0.48, 0.58, 0.45], dtype=np.float32)


def plasma_rgba(norm: np.ndarray, alpha: float = 0.88) -> np.ndarray:
    norm = np.clip(np.asarray(norm, np.float32).ravel(), 0.0, 1.0)
    out = np.zeros((len(norm), 4), np.float32)
    for i in range(len(_PT) - 1):
        lo, hi = _PT[i], _PT[i + 1]
        mask = (norm >= lo) & (norm <= hi)
        if not mask.any():
            continue
        u = (norm[mask] - lo) / (hi - lo + 1e-10)
        out[mask, :3] = _PC[i] + u[:, None] * (_PC[i + 1] - _PC[i])
    out[:, 3] = alpha
    return out


def load_manifest(frames_dir: Path) -> dict:
    path = frames_dir / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text())


def make_faces(grid_size: int) -> np.ndarray:
    faces = []
    for i in range(grid_size - 1):
        for j in range(grid_size - 1):
            k = i * grid_size + j
            faces.append([k, k + 1, k + grid_size])
            faces.append([k + 1, k + grid_size + 1, k + grid_size])
    return np.array(faces, dtype=np.uint32)


def normalize_values(values: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
    if vmax <= vmin:
        vmax = vmin + 1e-6
    return np.clip((values - vmin) / (vmax - vmin), 0.0, 1.0)


def frame_path_from_record(record: dict, cwd: Path) -> Path:
    p = Path(record["path"])
    if p.is_absolute() and p.exists():
        return p
    if p.exists():
        return p
    candidate = cwd / p
    if candidate.exists():
        return candidate
    return p


def load_frame_npz(path: Path) -> dict:
    d = np.load(path, allow_pickle=True)
    return {k: d[k] for k in d.files}


def build_vertices_and_colors(frame: dict, manifest: dict, alpha: float) -> tuple[np.ndarray, np.ndarray]:
    gx = frame["grid_x"].astype(np.float32)
    gy = frame["grid_y"].astype(np.float32)
    gz = frame["grid_z"].astype(np.float32)
    gc = frame["grid_color"].astype(np.float32)
    vertices = np.zeros((gx.size, 3), dtype=np.float32)
    vertices[:, 0] = gx.ravel()
    vertices[:, 1] = gy.ravel()
    finite_z = np.isfinite(gz)
    vertices[:, 2] = np.where(finite_z, gz, 0.0).ravel()
    lim = manifest.get("global_limits", {})
    finite_gc = gc[np.isfinite(gc)]
    fallback_min = float(np.nanpercentile(finite_gc, 1)) if finite_gc.size else -1.0
    fallback_max = float(np.nanpercentile(finite_gc, 99)) if finite_gc.size else 1.0
    cmin = float(lim.get("color_min", fallback_min))
    cmax = float(lim.get("color_max", fallback_max))
    c_clean = np.where(np.isfinite(gc), gc, cmin)
    colors = plasma_rgba(normalize_values(c_clean.ravel(), cmin, cmax), alpha=alpha)
    colors[~np.isfinite(gz.ravel()), 3] = 0.0
    return vertices, colors


class MarketFabricVisualizer:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.frames_root = Path(args.frames_dir)
        self.manifest = load_manifest(self.frames_root)
        self.frame_records = self.manifest["frames"]
        if not self.frame_records:
            raise RuntimeError("Manifest has no frames.")
        self.grid_size = int(self.manifest["grid_size"])
        self.faces = make_faces(self.grid_size)
        self.safe_mode = bool(args.safe_mode)
        self.fps = min(args.fps, 20) if self.safe_mode else args.fps
        self.interval = 1.0 / max(1, self.fps)
        self.speed = max(1, args.speed)
        self.playing = True
        self.idx = 0
        self.alpha = min(args.alpha, 0.72) if self.safe_mode else args.alpha
        self.node_alpha = min(args.node_alpha, 0.60) if self.safe_mode else args.node_alpha
        self.max_labels = min(args.max_labels, 5) if self.safe_mode else args.max_labels
        self.axes_visible = not getattr(args, "hide_axes", False)
        self.hud_visible = not getattr(args, "hide_hud", False)
        self.axis_nodes = []
        self.colorbar_nodes = []

        self.recording = False
        self.record_root = Path(args.record_root)
        self.record_dir = None
        self.record_frames_dir = None
        self.record_count = 0

        first = self._load_frame(0)
        vertices, colors = build_vertices_and_colors(first, self.manifest, self.alpha)

        self.canvas = scene.SceneCanvas(
            title="Market Fabric Visualizer", keys="interactive", bgcolor="#04070d", size=(1500, 950), show=True
        )
        self.canvas.events.key_press.connect(self._on_key)
        self.view = self.canvas.central_widget.add_view()
        self._cam_defaults = dict(fov=50, azimuth=38, elevation=28, distance=3.2, translate_speed=1.5)
        self.cam = NavigableCamera(**self._cam_defaults)
        self.view.camera = self.cam
        self.cam.interactive = True

        if args.wire_grid:
            self._add_reference_grid(first)

        self._create_axes_and_colorbar(first)

        self.mesh = visuals.Mesh(vertices=vertices, faces=self.faces, vertex_colors=colors)
        self.mesh.set_gl_state("translucent", depth_test=True, blend=True)
        self.view.add(self.mesh)

        self.anchor_scatter = visuals.Markers()
        self.long_scatter = visuals.Markers()
        self.short_scatter = visuals.Markers()
        self.view.add(self.anchor_scatter)
        self.view.add(self.long_scatter)
        self.view.add(self.short_scatter)

        self.label_nodes = []
        if args.ticker_labels:
            for _ in range(self.max_labels * 2):
                node = Text("", color=tuple(LONG_RGBA), font_size=11, bold=True, anchor_x="center", anchor_y="bottom")
                self.view.add(node)
                self.label_nodes.append(node)

        self.hud_nodes = []
        self._create_hud()
        self._update_frame(first)

        self.timer = app.Timer(interval=self.interval)
        self.timer.connect(self._step)
        self.timer.start()

        params = self.manifest.get("parameters", {})
        lims = self.manifest.get("global_limits", {})
        print("\n" + "─" * 78)
        print(" Market Fabric Visualizer | VisPy playback")
        print("─" * 78)
        print(f" frames       : {len(self.frame_records)}")
        print(f" grid         : {self.grid_size}² vertices={self.grid_size**2:,} faces={len(self.faces):,}")
        print(f" z/color      : {params.get('z_mode')} / {params.get('color_mode')}")
        print(f" period       : {params.get('start_date')} → {params.get('end_date')}")
        print(f" fps/speed    : {self.fps} fps | {self.speed} frame(s)/tick")
        print(f" safe mode    : {self.safe_mode}")
        print(f" z lim        : {float(lims.get('z_min', 0)):.4f} → {float(lims.get('z_max', 0)):.4f}")
        print(f" color lim    : {float(lims.get('color_min', 0)):.4f} → {float(lims.get('color_max', 0)):.4f}")
        print(" controls     : Space pause | +/- speed | H HUD | T axes | 1/2/3 cameras | V record | Q quit")
        print("─" * 78 + "\n")

    def _load_frame(self, idx: int) -> dict:
        rec = self.frame_records[idx % len(self.frame_records)]
        return load_frame_npz(frame_path_from_record(rec, Path.cwd()))

    def _add_reference_grid(self, frame: dict) -> None:
        gx, gy = frame["grid_x"], frame["grid_y"]
        gz = np.where(np.isfinite(frame["grid_z"]), frame["grid_z"], 0)
        z0 = float(np.nanpercentile(gz, 5))
        x_min, x_max = float(np.nanmin(gx)), float(np.nanmax(gx))
        y_min, y_max = float(np.nanmin(gy)), float(np.nanmax(gy))
        for frac in np.linspace(0, 1, 6):
            x = x_min + frac * (x_max - x_min)
            line = Line(width=0.7)
            line.set_data(np.array([[x, y_min, z0], [x, y_max, z0]], dtype=np.float32), color=(0.35, 0.55, 0.85, 0.18))
            self.view.add(line)
            y = y_min + frac * (y_max - y_min)
            line = Line(width=0.7)
            line.set_data(np.array([[x_min, y, z0], [x_max, y, z0]], dtype=np.float32), color=(0.35, 0.55, 0.85, 0.18))
            self.view.add(line)


    def _scene_bounds(self, frame: dict) -> tuple[float, float, float, float, float, float]:
        gx = frame["grid_x"]
        gy = frame["grid_y"]
        gz = frame["grid_z"]

        x_min, x_max = float(np.nanmin(gx)), float(np.nanmax(gx))
        y_min, y_max = float(np.nanmin(gy)), float(np.nanmax(gy))

        lim = self.manifest.get("global_limits", {})
        finite_gz = gz[np.isfinite(gz)]
        z_min = float(lim.get("z_min", np.nanpercentile(finite_gz, 1) if len(finite_gz) else -1.0))
        z_max = float(lim.get("z_max", np.nanpercentile(finite_gz, 99) if len(finite_gz) else 1.0))

        if z_max <= z_min:
            z_max = z_min + 1e-6

        return x_min, x_max, y_min, y_max, z_min, z_max

    def _add_line(self, pts: np.ndarray, color, width: float = 1.0):
        line = Line(width=width)
        line.set_data(np.asarray(pts, dtype=np.float32), color=color)
        self.view.add(line)
        return line

    def _add_text(self, text: str, pos, color=(0.8, 0.9, 1.0, 0.9), size=10, bold=False):
        node = Text(
            text,
            pos=pos,
            color=color,
            font_size=size,
            bold=bold,
            anchor_x="center",
            anchor_y="center",
        )
        self.view.add(node)
        return node

    def _create_axes_and_colorbar(self, frame: dict) -> None:
        params = self.manifest.get("parameters", {})
        z_mode = params.get("z_mode", "z")
        color_mode = params.get("color_mode", "color")

        x_min, x_max, y_min, y_max, z_min, z_max = self._scene_bounds(frame)

        xr = x_max - x_min + 1e-8
        yr = y_max - y_min + 1e-8
        zr = z_max - z_min + 1e-8

        x0 = x_min - 0.07 * xr
        y0 = y_min - 0.07 * yr
        z0 = z_min - 0.06 * zr

        x_axis_end = x_max + 0.05 * xr
        y_axis_end = y_max + 0.05 * yr
        z_axis_end = z_max + 0.12 * zr

        cyan = (0.0, 0.85, 1.0, 0.70)
        violet = (0.65, 0.45, 1.0, 0.70)
        gold = (1.0, 0.78, 0.16, 0.75)
        tick_color = (0.75, 0.86, 1.0, 0.72)

        self.axis_nodes.append(self._add_line([[x0, y0, z0], [x_axis_end, y0, z0]], cyan, 1.8))
        self.axis_nodes.append(self._add_line([[x0, y0, z0], [x0, y_axis_end, z0]], violet, 1.8))
        self.axis_nodes.append(self._add_line([[x0, y0, z0], [x0, y0, z_axis_end]], gold, 1.8))

        self.axis_nodes.append(self._add_text("Correlation X", (x_axis_end, y0, z0), cyan, 11, True))
        self.axis_nodes.append(self._add_text("Correlation Y", (x0, y_axis_end, z0), violet, 11, True))
        self.axis_nodes.append(self._add_text(f"Z: {z_mode}", (x0, y0, z_axis_end), gold, 11, True))

        for val in np.linspace(x_min, x_max, 5):
            self.axis_nodes.append(self._add_line([[val, y0, z0], [val, y0 - 0.018 * yr, z0]], cyan, 0.8))
            self.axis_nodes.append(self._add_text(f"{val:+.2f}", (val, y0 - 0.055 * yr, z0), tick_color, 8))

        for val in np.linspace(y_min, y_max, 5):
            self.axis_nodes.append(self._add_line([[x0, val, z0], [x0 - 0.018 * xr, val, z0]], violet, 0.8))
            self.axis_nodes.append(self._add_text(f"{val:+.2f}", (x0 - 0.06 * xr, val, z0), tick_color, 8))

        for val in np.linspace(z_min, z_max, 5):
            self.axis_nodes.append(self._add_line([[x0, y0, val], [x0 - 0.018 * xr, y0, val]], gold, 0.8))
            self.axis_nodes.append(self._add_text(f"{val:+.2f}", (x0 - 0.065 * xr, y0, val), tick_color, 8))

        lim = self.manifest.get("global_limits", {})
        c_min = float(lim.get("color_min", -1.0))
        c_max = float(lim.get("color_max", 1.0))

        cb_x = x_max + 0.13 * xr
        cb_y = y_max + 0.03 * yr
        cb_z0 = z_min
        cb_z1 = z_max

        n_seg = 24
        for i in range(n_seg):
            a = i / n_seg
            b = (i + 1) / n_seg
            c = plasma_rgba(np.array([(a + b) * 0.5]), alpha=0.95)[0]
            za = cb_z0 + a * (cb_z1 - cb_z0)
            zb = cb_z0 + b * (cb_z1 - cb_z0)
            self.colorbar_nodes.append(self._add_line([[cb_x, cb_y, za], [cb_x, cb_y, zb]], tuple(c), 5.0))

        self.colorbar_nodes.append(self._add_text(f"Color: {color_mode}", (cb_x, cb_y, cb_z1 + 0.08 * zr), (0.90, 0.94, 1.0, 0.95), 10, True))
        self.colorbar_nodes.append(self._add_text(f"{c_max:+.2f}", (cb_x + 0.055 * xr, cb_y, cb_z1), (0.90, 0.94, 1.0, 0.85), 8))
        self.colorbar_nodes.append(self._add_text(f"{c_min:+.2f}", (cb_x + 0.055 * xr, cb_y, cb_z0), (0.90, 0.94, 1.0, 0.85), 8))

    def _set_axes_visible(self, visible: bool) -> None:
        self.axes_visible = visible
        for node in self.axis_nodes + self.colorbar_nodes:
            node.visible = visible

    def _set_hud_visible(self, visible: bool) -> None:
        self.hud_visible = visible
        for node in self.hud_nodes:
            node.visible = visible


    def _create_hud(self) -> None:
        x0, y0, z0, dz = 0.65, 0.45, 0.25, 0.05
        for i in range(12):
            color, size, bold = (0.82, 0.90, 1.0, 0.92), 10, False
            if i == 0:
                color, size, bold = (0.0, 0.92, 1.0, 1.0), 15, True
            elif i == 1:
                color = (0.55, 0.75, 0.95, 0.85)
            node = Text("", pos=(x0, y0, z0 - i * dz), color=color, font_size=size, bold=bold, anchor_x="left")
            self.view.add(node)
            self.hud_nodes.append(node)

    def _update_mesh(self, frame: dict) -> None:
        vertices, colors = build_vertices_and_colors(frame, self.manifest, self.alpha)
        self.mesh.set_data(vertices=vertices, faces=self.faces, vertex_colors=colors)

    def _update_anchors(self, frame: dict) -> None:
        x = frame["anchor_x"].astype(np.float32)
        y = frame["anchor_y"].astype(np.float32)
        z = frame["anchor_z"].astype(np.float32)
        is_long = frame["is_long"].astype(bool)
        is_short = frame["is_short"].astype(bool)
        conf = frame["anchor_conf"].astype(np.float32)
        z_span = float(np.nanmax(z) - np.nanmin(z)) if np.isfinite(z).any() else 1.0
        lift = max(0.01, 0.025 * z_span)
        pos = np.column_stack([x, y, z + lift]).astype(np.float32)
        peer = ~(is_long | is_short)
        self.anchor_scatter.set_data(pos[peer] if peer.any() else np.zeros((0, 3), np.float32), face_color=(0.48, 0.50, 0.62, self.node_alpha * 0.45), edge_color=(0.48, 0.50, 0.62, 0.05), size=3.0 if self.safe_mode else 4.0)
        if is_long.any():
            self.long_scatter.set_data(pos[is_long], face_color=tuple(LONG_RGBA), edge_color=(1, 1, 1, 0.85), size=8.0 + 2.0 * np.clip(conf[is_long], 0, 6))
        else:
            self.long_scatter.set_data(np.zeros((0, 3), np.float32), size=1)
        if is_short.any():
            self.short_scatter.set_data(pos[is_short], face_color=tuple(SHORT_RGBA), edge_color=(1, 1, 1, 0.85), size=8.0 + 2.0 * np.clip(conf[is_short], 0, 6))
        else:
            self.short_scatter.set_data(np.zeros((0, 3), np.float32), size=1)

    def _update_labels(self, frame: dict) -> None:
        if not self.label_nodes:
            return
        tickers = [str(t) for t in frame["tickers"].tolist()]
        x, y, z = frame["anchor_x"], frame["anchor_y"], frame["anchor_z"]
        conf = frame["anchor_conf"].astype(np.float32)
        is_long = frame["is_long"].astype(bool)
        is_short = frame["is_short"].astype(bool)
        signal_idx = np.where(is_long | is_short)[0]
        order = signal_idx[np.argsort(conf[signal_idx])[::-1]] if len(signal_idx) else np.array([], dtype=int)
        z_span = float(np.nanmax(z) - np.nanmin(z)) if np.isfinite(z).any() else 1.0
        dz = max(0.02, 0.06 * z_span)
        for k, node in enumerate(self.label_nodes):
            if k >= len(order) or k >= self.max_labels:
                node.text = ""
                continue
            i = int(order[k])
            marker = "L:" if is_long[i] else "S:"
            node.text = f"{marker}{tickers[i]}"
            node.pos = (float(x[i]), float(y[i]), float(z[i] + dz))
            node.color = tuple(LONG_RGBA if is_long[i] else SHORT_RGBA)

    def _update_hud(self, frame: dict) -> None:
        params = self.manifest.get("parameters", {})
        date = str(frame.get("date", "?"))
        regime = str(frame.get("ctx_regime", "UNKNOWN"))
        vol_z = float(frame.get("ctx_vol_z", 0.0))
        ent_z = float(frame.get("ctx_ent_z", 0.0))
        is_long = frame["is_long"].astype(bool)
        is_short = frame["is_short"].astype(bool)
        tickers = np.array([str(t) for t in frame["tickers"].tolist()])
        conf = frame["anchor_conf"].astype(np.float32)
        def top_names(mask, n=5):
            idx = np.where(mask)[0]
            if len(idx) == 0:
                return "none"
            idx = idx[np.argsort(conf[idx])[::-1]][:n]
            return ", ".join(tickers[idx].tolist())
        lines = [
            "MARKET FABRIC",
            f"{'PLAY' if self.playing else 'PAUSE'} | speed={self.speed} | recording={'REC' if self.recording else 'off'}",
            f"Date       : {date}",
            f"Frame      : {self.idx + 1}/{len(self.frame_records)}",
            f"X/Y        : rolling correlation embedding",
            f"Z height   : {params.get('z_mode')}",
            f"Heat/color : {params.get('color_mode')}",
            f"Regime     : {regime}",
            f"Vol z      : {vol_z:+.2f} | Ent z: {ent_z:+.2f}",
            f"Cyan      : long signal valleys",
            f"Red       : short signal spikes",
            f"Longs      : {top_names(is_long)}",
        ]
        for node, text in zip(self.hud_nodes, lines):
            node.text = text

    def _update_frame(self, frame=None) -> None:
        frame = self._load_frame(self.idx) if frame is None else frame
        self._update_mesh(frame)
        self._update_anchors(frame)
        self._update_labels(frame)
        self._update_hud(frame)

    def _step(self, event) -> None:
        if not self.playing:
            return
        self.idx = (self.idx + self.speed) % len(self.frame_records)
        self._update_frame(self._load_frame(self.idx))
        if self.recording:
            self._record_frame()
        self.canvas.update()

    def _save_canvas_png(self, path: Path) -> None:
        self.canvas.update()
        write_png(str(path), self.canvas.render(alpha=False))

    def _start_recording(self) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = self.frames_root.name
        self.record_dir = self.record_root / f"{run_name}_{ts}"
        self.record_frames_dir = self.record_dir / "frames"
        self.record_frames_dir.mkdir(parents=True, exist_ok=True)
        self.record_count = 0
        self.recording = True
        print(f"[record] started -> {self.record_dir}")

    def _stop_recording(self) -> None:
        self.recording = False
        print(f"[record] stopped | frames={self.record_count}")
        if not self.record_frames_dir or self.record_count == 0:
            return
        try:
            import imageio.v3 as iio
            frames = sorted(self.record_frames_dir.glob("frame_*.png"))
            images = [iio.imread(p) for p in frames]
            mp4 = self.record_dir / "playback.mp4"
            gif = self.record_dir / "playback.gif"
            iio.imwrite(mp4, images, fps=self.fps)
            iio.imwrite(gif, images, fps=self.fps)
            print(f"[record] mp4 -> {mp4}")
            print(f"[record] gif -> {gif}")
        except Exception as exc:
            print("[record] saved PNG frames; could not auto-build video.")
            print(f"[record] reason: {exc}")
            print("[record] manual ffmpeg command:")
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
            print(f"[animation] {'playing' if self.playing else 'paused'}")
            self._update_frame()
            self.canvas.update()

        elif key in ("+", "=", "PLUS", "]"):
            self.speed += 1
            print(f"[speed] {self.speed}")
            self._update_frame()
            self.canvas.update()

        elif key in ("-", "_", "MINUS", "["):
            self.speed = max(1, self.speed - 1)
            print(f"[speed] {self.speed}")
            self._update_frame()
            self.canvas.update()

        elif key == "H":
            self._set_hud_visible(not self.hud_visible)
            print(f"[hud] {'on' if self.hud_visible else 'off'}")
            self.canvas.update()

        elif key == "T":
            self._set_axes_visible(not self.axes_visible)
            print(f"[axes] {'on' if self.axes_visible else 'off'}")
            self.canvas.update()

        elif key == "1":
            self.cam.azimuth = 38
            self.cam.elevation = 28
            self.cam.distance = 3.2
            self.canvas.update()

        elif key == "2":
            self.cam.azimuth = 0
            self.cam.elevation = 89
            self.cam.distance = 3.2
            self.canvas.update()

        elif key == "3":
            self.cam.azimuth = 90
            self.cam.elevation = 8
            self.cam.distance = 3.2
            self.canvas.update()

        elif key == "V":
            self._toggle_recording()
            self._update_frame()
            self.canvas.update()

        elif key == "S" and "Shift" in [m.name for m in (event.modifiers or [])]:
            filename = Path(f"market_fabric_{datetime.now():%Y%m%d_%H%M%S}.png")
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

    # Keep a strong reference alive.
    # Without this, Python may garbage-collect the visualizer/timer/callbacks,
    # leaving the first frame visible but animation and controls dead.
    _VIZ = MarketFabricVisualizer(args)

    app.run()


if __name__ == "__main__":
    main()
