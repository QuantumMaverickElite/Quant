"""
GARCH Volatility Field Visualizer v10
=====================================

Stable alpha-reveal animation.

This version fixes the animation problem by avoiding topology changes.

Core idea:
  1. Compute GARCH metrics once.
  2. Build the complete surface once.
  3. Create one Mesh object once.
  4. Keep the same vertices and faces forever.
  5. Animate only vertex alpha values.

Why this works better:
  - No griddata inside the animation loop.
  - No gaussian_filter inside the animation loop.
  - No Mesh recreation inside the animation loop.
  - No changing faces/topology inside the animation loop.
  - Only vertex colors change each frame.

Behavior:
  - Surface starts invisible.
  - Each tick reveals one more trading bar.
  - Loops automatically.
  - HUD and cursor update with the current bar.

Controls:
  LMB drag          : orbit
  RMB drag          : pan
  Scroll            : zoom
  W/S or Up/Down    : tilt elevation
  A/D or Left/Right : rotate azimuth
  R                 : reset camera
  Space             : pause / play animation
  + / =             : increase animation speed
  - / _             : decrease animation speed
  V                 : start / stop recording frames
  Shift+S           : screenshot
  Q / Esc           : quit

Recording:
  Press V to start recording frames.
  Press V again to stop recording.

  Frames save into:
      outputs/garch_recordings/<ticker>_<timestamp>/frames

  Optional install for automatic mp4/gif:
      pip install imageio imageio-ffmpeg
"""

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter

from vispy import app, scene
from vispy.io import write_png
from vispy.scene import visuals
from vispy.scene.cameras import TurntableCamera
from vispy.scene.visuals import Line, Text

# -------------------------
# GLOBAL CONSTANTS
# -------------------------
VOL_SCALE = 0.50
REGIME_AXIS_SCALE = 0.25

SURFACE_RES_Y = 110
SMOOTH_SIGMA = 1.6
LINE_SMOOTH = 8

# 0.03 is safer than 0.01 for interactive VisPy rendering.
# Use speed controls to make playback faster after confirming it works.
ANIMATION_INTERVAL = 0.03
ANIMATION_SPEED = 1
ANIMATION_LOOP_START = 2

RECORD_ROOT = Path("outputs/garch_recordings")
RECORD_EVERY_N_FRAMES = 1
RECORD_FPS = 60

DEBUG_ANIMATION = True
DEBUG_EVERY_N_FRAMES = 60


# -------------------------
# GARCH BACKEND
# -------------------------
try:
    from backtester.analytics.volatility import compute_garch_metrics

    _USING_REAL_GARCH = True
except ImportError:
    _USING_REAL_GARCH = False

    def compute_garch_metrics(price_series: pd.Series) -> pd.DataFrame:
        prices = pd.Series(np.asarray(price_series).squeeze(), name="close")
        prices = prices.dropna().astype(float)

        ret = np.log(prices / prices.shift(1)).dropna()
        rv = ret.rolling(21).std().reindex(prices.index).bfill().ffill()

        df = prices.to_frame("close")
        df["log_return"] = np.log(prices / prices.shift(1))
        df["garch_vol"] = rv
        df["garch_vol_annualized"] = rv * np.sqrt(252)
        df["vol_zscore"] = (rv - rv.rolling(100).mean()) / (
            rv.rolling(100).std() + 1e-10
        )
        df["vol_percentile"] = rv.rolling(252).rank(pct=True)
        df["vol_of_vol"] = rv.rolling(20).std()
        df["vol_change_pct"] = rv.pct_change()

        z = df["vol_zscore"]
        regime = pd.Series("NORMAL", index=df.index, dtype=object)
        regime[z < -1.0] = "LOW"
        regime[z > 1.5] = "HIGH"

        df["vol_regime"] = regime
        df["vol_spike_flag"] = (
            (df["vol_change_pct"] > 0.10) & (z > 1.5) & (df["vol_percentile"] > 0.70)
        )
        df["vol_high_flag"] = df["vol_percentile"] > 0.80

        return df.dropna(subset=["garch_vol", "vol_zscore"])


# -------------------------
# CAMERA
# -------------------------
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
        step_az = 3.0
        step_elev = 2.0
        key = (event.key.name or "").upper()

        if key in ("A", "LEFT"):
            self.azimuth -= step_az
        elif key in ("D", "RIGHT"):
            self.azimuth += step_az
        elif key in ("W", "UP"):
            self.elevation = np.clip(self.elevation + step_elev, -89, 89)
        elif key in ("S", "DOWN"):
            self.elevation = np.clip(self.elevation - step_elev, -89, 89)

        self.view_changed()


# -------------------------
# COLOR MAP
# -------------------------
_PT = np.array(
    [0.00, 0.12, 0.28, 0.44, 0.58, 0.70, 0.82, 0.93, 1.00],
    dtype=np.float32,
)

_PC = np.array(
    [
        [0.02, 0.01, 0.14],
        [0.14, 0.03, 0.60],
        [0.00, 0.42, 0.92],
        [0.00, 0.82, 0.82],
        [0.12, 0.88, 0.25],
        [0.96, 0.84, 0.00],
        [1.00, 0.38, 0.00],
        [1.00, 0.08, 0.08],
        [1.00, 0.96, 0.96],
    ],
    dtype=np.float32,
)


def plasma(norm: np.ndarray) -> np.ndarray:
    norm = np.clip(np.asarray(norm, np.float32).ravel(), 0, 1)
    out = np.zeros((len(norm), 4), np.float32)

    for i in range(len(_PT) - 1):
        lo, hi = _PT[i], _PT[i + 1]
        mask = (norm >= lo) & (norm <= hi)

        if not mask.any():
            continue

        u = (norm[mask] - lo) / (hi - lo + 1e-10)
        out[mask, :3] = _PC[i] + u[:, None] * (_PC[i + 1] - _PC[i])

    out[:, 3] = 0.92 + 0.08 * np.sin(norm * np.pi)
    return out


# -------------------------
# DATA PREP
# -------------------------
def prepare_field(df: pd.DataFrame):
    v_raw = df["garch_vol_annualized"].values.astype(np.float32)

    z_raw = np.clip(
        np.nan_to_num(df["vol_zscore"].values.astype(np.float32)),
        -3,
        3,
    )

    z_scaled = z_raw * REGIME_AXIS_SCALE

    # One normalized coordinate per trading bar.
    t = np.linspace(0.0, 1.0, len(df), dtype=np.float32)

    v_norm = (v_raw - v_raw.min()) / (v_raw.max() - v_raw.min() + 1e-8)
    v_scaled = v_norm * VOL_SCALE

    return t, z_raw, z_scaled, v_raw, v_scaled


def raw_z_to_scaled(z_value: float) -> float:
    return float(z_value) * REGIME_AXIS_SCALE


# -------------------------
# PRECOMPUTED SURFACE
# -------------------------
def build_full_surface(t, z_scaled, v_scaled, res_y=SURFACE_RES_Y):
    """
    Build the full surface once.

    X resolution equals len(t), so each time column corresponds to one trading bar.
    """
    res_x = len(t)

    ti = np.asarray(t, dtype=np.float32)
    zi = np.linspace(-3, 3, res_y, dtype=np.float32) * REGIME_AXIS_SCALE

    T, Z = np.meshgrid(ti, zi)

    points = np.column_stack([t, z_scaled]).astype(np.float32)
    V_lin = griddata(points, v_scaled, (T, Z), method="linear", fill_value=np.nan)
    V_nn = griddata(points, v_scaled, (T, Z), method="nearest")

    V = np.where(np.isnan(V_lin), V_nn, V_lin)
    V = gaussian_filter(V.astype(np.float64), sigma=SMOOTH_SIGMA).astype(np.float32)

    norm = (V - V.min()) / max(V.max() - V.min(), 1e-6)

    vertices = np.column_stack([T.ravel(), Z.ravel(), V.ravel()]).astype(np.float32)
    base_colors = plasma(norm.ravel())

    rows, cols = T.shape
    faces = []

    for i in range(rows - 1):
        for j in range(cols - 1):
            k = i * cols + j
            faces.extend(
                [
                    [k, k + 1, k + cols],
                    [k + 1, k + cols + 1, k + cols],
                ]
            )

    return vertices, np.array(faces, dtype=np.uint32), base_colors, V, T, Z


# -------------------------
# GRID
# -------------------------
def add_reference_grid(view, v_raw, v_scaled):
    v_min, v_max = v_raw.min(), v_raw.max()
    vs_min, vs_max = v_scaled.min(), v_scaled.max()

    y_min = raw_z_to_scaled(-3)
    y_max = raw_z_to_scaled(3)

    def raw_vol_to_scaled(v):
        return (v - v_min) / (v_max - v_min + 1e-8) * VOL_SCALE

    v_range = v_max - v_min
    step = 0.05 if v_range < 0.30 else 0.10

    v_start = np.ceil(v_min / step) * step
    v_end = np.floor(v_max / step) * step

    for v_level in np.arange(v_start, v_end + step * 0.5, step):
        if v_level < v_min or v_level > v_max:
            continue

        vs = raw_vol_to_scaled(v_level)

        pts = np.array(
            [
                [0.0, y_min, vs],
                [1.0, y_min, vs],
                [1.0, y_max, vs],
                [0.0, y_max, vs],
                [0.0, y_min, vs],
            ],
            dtype=np.float32,
        )

        line = Line(width=1.0)
        line.set_data(pts, color=(0.4, 0.7, 1.0, 0.22))
        view.add(line)

    z_levels = [-2, -1, 0, 1, 2]
    z_colors = [
        (0.30, 0.55, 1.00, 0.35),
        (0.20, 0.80, 1.00, 0.28),
        (1.00, 1.00, 1.00, 0.30),
        (1.00, 0.75, 0.10, 0.28),
        (1.00, 0.20, 0.10, 0.35),
    ]

    for z_raw, color in zip(z_levels, z_colors):
        y = raw_z_to_scaled(z_raw)

        pts = np.array(
            [
                [0.0, y, vs_min],
                [1.0, y, vs_min],
                [1.0, y, vs_max],
                [0.0, y, vs_max],
                [0.0, y, vs_min],
            ],
            dtype=np.float32,
        )

        line = Line(width=1.2 if z_raw == 0 else 0.8)
        line.set_data(pts, color=color)
        view.add(line)

    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        pts = np.array(
            [
                [frac, y_min, vs_min],
                [frac, y_max, vs_min],
            ],
            dtype=np.float32,
        )

        line = Line(width=0.7)
        line.set_data(pts, color=(0.4, 0.55, 0.75, 0.18))
        view.add(line)


# -------------------------
# LABELS
# -------------------------
def add_axis_labels(view, v_raw, v_scaled, df, t):
    v_min, v_max = v_raw.min(), v_raw.max()
    vs_min, vs_max = v_scaled.min(), v_scaled.max()
    vs_mid = (vs_min + vs_max) * 0.5

    y_min = raw_z_to_scaled(-3)

    def raw_vol_to_scaled(v):
        return (v - v_min) / (v_max - v_min + 1e-8) * VOL_SCALE

    title_kw = dict(color=(1.0, 1.0, 1.0, 1.0), font_size=18, bold=True)
    tick_kw = dict(color=(0.80, 0.90, 1.0, 0.95), font_size=12, bold=False)

    view.add(
        Text(
            "TIME",
            pos=(0.5, y_min - 0.22, vs_min - 0.02),
            anchor_x="center",
            **title_kw,
        )
    )
    view.add(
        Text(
            "REGIME (z-score)", pos=(-0.14, 0.0, vs_min), anchor_x="center", **title_kw
        )
    )
    view.add(
        Text(
            "ANNUALISED VOL",
            pos=(-0.14, y_min - 0.22, vs_mid),
            anchor_x="center",
            **title_kw,
        )
    )

    v_range = v_max - v_min
    step = 0.05 if v_range < 0.30 else 0.10

    v_start = np.ceil(v_min / step) * step
    v_end = np.floor(v_max / step) * step

    for v_level in np.arange(v_start, v_end + step * 0.5, step):
        if v_level < v_min - 1e-4 or v_level > v_max + 1e-4:
            continue

        vs = raw_vol_to_scaled(v_level)
        view.add(
            Text(
                f"{v_level:.0%}",
                pos=(-0.10, y_min - 0.12, vs),
                anchor_x="right",
                **tick_kw,
            )
        )

    for z_raw in [-3, -2, -1, 0, 1, 2, 3]:
        y = raw_z_to_scaled(z_raw)
        view.add(
            Text(
                f"{z_raw:+d}σ",
                pos=(-0.08, y, vs_min - 0.015),
                anchor_x="center",
                **tick_kw,
            )
        )

    dates = pd.to_datetime(df.index)
    tick_idx = np.linspace(0, len(dates) - 1, 5).astype(int)
    for i in tick_idx:
        frac = t[i]
        label = dates[i].strftime("%Y-%m")
        view.add(
            Text(
                label,
                pos=(float(frac), y_min - 0.18, vs_min - 0.015),
                anchor_x="center",
                **tick_kw,
            )
        )


# -------------------------
# MAIN VISUALIZER
# -------------------------
class GarchFieldVisualizer:
    def __init__(self, df: pd.DataFrame, ticker: str = "SPY"):
        self.ticker = ticker
        self.df_full = df.copy()

        t, z_raw, z_scaled, v_raw, v_scaled = prepare_field(df)

        self.t = t
        self.z_raw = z_raw
        self.z_scaled = z_scaled
        self.v_raw = v_raw
        self.v_scaled = v_scaled

        self.max_idx = len(self.df_full)
        self.loop_start_idx = min(ANIMATION_LOOP_START, self.max_idx - 1)
        self.current_idx = self.loop_start_idx
        self.speed = ANIMATION_SPEED
        self.playing = True
        self.frame_count = 0

        self.recording = False
        self.record_dir = None
        self.record_frames_dir = None
        self.record_frame_count = 0
        self.record_tick_count = 0

        self.canvas = scene.SceneCanvas(
            title=f"GARCH Volatility Surface | {ticker}",
            keys="interactive",
            bgcolor="#04070d",
            size=(1500, 950),
            show=True,
        )

        self.canvas.events.key_press.connect(self._on_key)

        self.view = self.canvas.central_widget.add_view()

        self._cam_defaults = dict(
            fov=50,
            azimuth=38,
            elevation=28,
            distance=4.5,
            translate_speed=1.5,
        )

        self.cam = NavigableCamera(**self._cam_defaults)
        self.view.camera = self.cam
        self.cam.interactive = True

        # Static grid and labels only. No ghost surface.
        add_reference_grid(self.view, self.v_raw, self.v_scaled)
        add_axis_labels(self.view, self.v_raw, self.v_scaled, self.df_full, self.t)

        # Build full surface once.
        (
            self.vertices,
            self.faces,
            self.base_colors,
            self.full_V,
            self.full_T,
            self.full_Z,
        ) = build_full_surface(self.t, self.z_scaled, self.v_scaled)

        self.animated_colors = self.base_colors.copy()
        self.animated_colors[:, 3] = 0.0

        self.vertex_x = self.vertices[:, 0].copy()

        # Create surface mesh once. Same vertices/faces forever.
        self.mesh = visuals.Mesh(
            vertices=self.vertices,
            faces=self.faces,
            vertex_colors=self.animated_colors,
        )
        self.mesh.set_gl_state("translucent", depth_test=True, blend=True)
        self.view.add(self.mesh)

        # Dynamic overlays. These are small and can update safely.
        self.surface_line = Line(width=2.0)
        self.view.add(self.surface_line)

        self.floor_line = Line(width=1.2)
        self.view.add(self.floor_line)

        self.mid_line = Line(width=1.0)
        self.view.add(self.mid_line)

        self.cursor = Line(width=2.0)
        self.view.add(self.cursor)

        # One permanent batched spike visual. Do not create/remove spike nodes per frame.
        self.spike_batch = Line(connect="segments", width=1.5)
        self.view.add(self.spike_batch)

        self.hud_nodes = []
        self._create_hud_nodes()

        self._update_frame()

        self.timer = app.Timer(interval=ANIMATION_INTERVAL)
        self.timer.connect(self._step)
        self.timer.start()

        regime = self.df_full.iloc[-1].get("vol_regime", "?")
        src = "real GARCH" if _USING_REAL_GARCH else "rolling-std stub"

        print(f"\n{'─' * 72}")
        print(f"  {ticker} | GARCH Volatility Surface [{src}] | Alpha Reveal")
        print(f"{'─' * 72}")
        print(f"  Bars                  : {self.max_idx:,}")
        print(f"  Vertices              : {len(self.vertices):,}")
        print(f"  Faces                 : {len(self.faces):,}")
        print(
            f"  Playback              : {self.speed} bar per {ANIMATION_INTERVAL:.2f}s"
        )
        print(f"  Loop start            : {self.loop_start_idx}")
        print(f"  Ann. vol              : {self.v_raw[-1]:.2%} current")
        print(
            f"  Vol range             : {self.v_raw.min():.2%} -> {self.v_raw.max():.2%}"
        )
        print(f"  Z-score               : {self.z_raw[-1]:+.2f} sigma")
        print(f"  Regime                : {regime}")
        print(
            f"  Controls              : Space pause/play | +/- speed | V record | Shift+S screenshot"
        )
        print(f"{'─' * 72}\n")

    def _create_hud_nodes(self):
        y_hud = raw_z_to_scaled(3) + 0.30
        x0 = 1.12
        z0 = float(self.v_scaled.max()) + 0.02
        dz = VOL_SCALE * 0.075

        for i in range(12):
            color = (0.80, 0.90, 1.0, 0.90)
            size = 11
            bold = False

            if i == 0:
                color = (0.00, 0.92, 1.00, 1.00)
                size = 16
                bold = True
            elif i == 1:
                color = (0.40, 0.70, 0.90, 0.80)
                size = 10
            elif i == 11:
                color = (1.00, 0.55, 0.15, 0.95)

            node = Text(
                "",
                pos=(x0, y_hud, z0 - i * dz),
                color=color,
                font_size=size,
                bold=bold,
                anchor_x="left",
            )
            self.view.add(node)
            self.hud_nodes.append(node)

    def _visible_idx(self):
        return int(np.clip(self.current_idx, self.loop_start_idx, self.max_idx))

    def _update_surface_alpha(self, idx):
        current_x = float(self.t[idx - 1])

        # Vertex visibility only. Same mesh topology forever.
        visible = self.vertex_x <= current_x
        self.animated_colors[:, 3] = 0.0
        self.animated_colors[visible, 3] = self.base_colors[visible, 3]

        # Update colors while keeping vertices/faces unchanged.
        self.mesh.set_data(
            vertices=self.vertices,
            faces=self.faces,
            vertex_colors=self.animated_colors,
        )

    def _update_lines(self, idx):
        t = self.t[:idx]
        z_scaled = self.z_scaled[:idx]
        v_scaled = self.v_scaled[:idx]

        if len(t) < 3:
            empty = np.zeros((0, 3), dtype=np.float32)
            self.surface_line.set_data(empty, color=(1.0, 0.85, 0.12, 0.75))
            self.floor_line.set_data(empty, color=(0.0, 0.85, 1.0, 0.45))
            self.mid_line.set_data(empty, color=(1.0, 1.0, 1.0, 0.28))
            return

        z_sm = gaussian_filter(z_scaled.astype(np.float64), sigma=LINE_SMOOTH).astype(
            np.float32
        )
        vs_sm = gaussian_filter(v_scaled.astype(np.float64), sigma=LINE_SMOOTH).astype(
            np.float32
        )

        pts_surface = np.column_stack([t, z_sm, vs_sm]).astype(np.float32)
        self.surface_line.set_data(pts_surface, color=(1.0, 0.85, 0.12, 0.75))

        vs_floor = float(v_scaled.min()) - 0.003
        pts_floor = pts_surface.copy()
        pts_floor[:, 2] = vs_floor
        self.floor_line.set_data(pts_floor, color=(0.0, 0.85, 1.0, 0.45))

        vs_mid = float((v_scaled.max() + v_scaled.min()) * 0.5)
        pts_mid = np.column_stack([t, z_sm, np.full(len(t), vs_mid)]).astype(np.float32)
        self.mid_line.set_data(pts_mid, color=(1.0, 1.0, 1.0, 0.28))

    def _update_cursor(self, idx):
        x = float(self.t[idx - 1])
        y_min = raw_z_to_scaled(-3)
        y_max = raw_z_to_scaled(3)
        z_min = float(self.v_scaled.min())
        z_max = float(self.v_scaled.max())

        pts = np.array(
            [
                [x, y_min, z_min],
                [x, y_max, z_min],
                [x, y_max, z_max],
                [x, y_min, z_max],
                [x, y_min, z_min],
            ],
            dtype=np.float32,
        )
        self.cursor.set_data(pts, color=(1.0, 1.0, 1.0, 0.45))

    def _update_spikes(self, idx):
        t = self.t[:idx]
        z_raw = self.z_raw[:idx]
        z_scaled = self.z_scaled[:idx]
        v_scaled = self.v_scaled[:idx]

        spike_idx = np.where(np.abs(z_raw) > 2.0)[0]

        keep = []
        for i in spike_idx:
            if not keep or i - keep[-1] > 8:
                keep.append(i)

        if not keep:
            self.spike_batch.set_data(
                pos=np.zeros((0, 3), dtype=np.float32),
                color=(1.0, 0.2, 0.1, 0.0),
            )
            return

        vs_floor = float(v_scaled.min())
        pts = []
        colors = []

        for i in keep:
            color = (1.0, 0.18, 0.05, 0.80) if z_raw[i] > 0 else (0.18, 0.55, 1.0, 0.80)
            pts.append([t[i], z_scaled[i], vs_floor])
            pts.append([t[i], z_scaled[i], float(v_scaled[i])])
            colors.append(color)
            colors.append(color)

        self.spike_batch.set_data(
            pos=np.array(pts, dtype=np.float32),
            color=np.array(colors, dtype=np.float32),
        )

    def _update_hud(self, idx):
        df_slice = self.df_full.iloc[:idx]
        v_raw = self.v_raw[:idx]
        snap = df_slice.iloc[-1]

        cur_date = pd.to_datetime(df_slice.index[-1]).strftime("%Y-%m-%d")
        cur_z = float(snap.get("vol_zscore", 0))
        regime = str(snap.get("vol_regime", "N/A"))
        spike = bool(snap.get("vol_spike_flag", False))
        high = bool(snap.get("vol_high_flag", False))
        vov = snap.get("vol_of_vol", np.nan)
        vpct = snap.get("vol_percentile", np.nan)

        flags = ("SPIKE " if spike else "") + ("HIGH" if high else "") or "none"
        src = "GARCH" if _USING_REAL_GARCH else "rolling-std"
        state = "PLAY" if self.playing else "PAUSE"
        rec_state = "REC" if self.recording else "off"

        texts = [
            f"{self.ticker} GARCH VOL SURFACE",
            f"[{src}] {state} | speed={self.speed} bar/tick | recording={rec_state}",
            f"Date       : {cur_date}",
            f"Progress   : {idx:,}/{self.max_idx:,}",
            f"Ann. vol   : {v_raw[-1]:.1%}",
            f"Mean vol   : {v_raw.mean():.1%}",
            f"Peak vol   : {v_raw.max():.1%}",
            "Vol-of-vol : "
            + (
                f"{float(vov) * np.sqrt(252):.1%}"
                if not (isinstance(vov, float) and np.isnan(vov))
                else "--"
            ),
            "Percentile : "
            + (
                f"{float(vpct):.0%}"
                if not (isinstance(vpct, float) and np.isnan(vpct))
                else "--"
            ),
            f"Z-score    : {cur_z:+.2f}s",
            f"Regime     : {regime}",
            f"Flags      : {flags}",
        ]

        for node, text in zip(self.hud_nodes, texts):
            node.text = text

    def _update_frame(self):
        idx = self._visible_idx()
        self._update_surface_alpha(idx)
        self._update_lines(idx)
        self._update_cursor(idx)
        self._update_spikes(idx)
        self._update_hud(idx)

    def _step(self, event):
        if not self.playing:
            return

        self.frame_count += 1
        self.current_idx += self.speed

        if self.current_idx >= self.max_idx:
            self.current_idx = self.loop_start_idx

        if DEBUG_ANIMATION and self.frame_count % DEBUG_EVERY_N_FRAMES == 0:
            print(f"[anim] idx={self.current_idx}/{self.max_idx}")

        self._update_frame()

        if self.recording:
            self._record_frame_if_needed()

        self.canvas.update()

    # -------------------------
    # RECORDING
    # -------------------------
    def _toggle_recording(self):
        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.record_dir = RECORD_ROOT / f"{self.ticker}_{timestamp}"
        self.record_frames_dir = self.record_dir / "frames"
        self.record_frames_dir.mkdir(parents=True, exist_ok=True)

        self.recording = True
        self.record_frame_count = 0
        self.record_tick_count = 0

        print(f"[recording] started -> {self.record_dir}")

    def _stop_recording(self):
        self.recording = False
        print(f"[recording] stopped | frames={self.record_frame_count}")

        if self.record_frame_count == 0:
            print("[recording] no frames captured")
            return

        self._try_build_video_files()

    def _save_canvas_png(self, path):
        # SceneCanvas does not always provide .save() depending on VisPy version.
        # render() + write_png() is the stable way to capture the current frame.
        self.canvas.update()
        image = self.canvas.render(alpha=False)
        write_png(str(path), image)

    def _record_frame_if_needed(self):
        self.record_tick_count += 1

        if self.record_tick_count % RECORD_EVERY_N_FRAMES != 0:
            return

        if self.record_frames_dir is None:
            return

        frame_path = self.record_frames_dir / f"frame_{self.record_frame_count:05d}.png"
        self._save_canvas_png(frame_path)
        self.record_frame_count += 1

    def _try_build_video_files(self):
        if self.record_dir is None or self.record_frames_dir is None:
            return

        frames = sorted(self.record_frames_dir.glob("frame_*.png"))
        if not frames:
            return

        try:
            import imageio.v3 as iio

            images = [iio.imread(frame) for frame in frames]

            mp4_path = self.record_dir / "playback.mp4"
            gif_path = self.record_dir / "playback.gif"

            iio.imwrite(mp4_path, images, fps=RECORD_FPS)
            iio.imwrite(gif_path, images, fps=RECORD_FPS)

            print(f"[recording] mp4 -> {mp4_path}")
            print(f"[recording] gif -> {gif_path}")
        except Exception as exc:
            print("[recording] saved PNG frames successfully")
            print("[recording] could not auto-build mp4/gif")
            print(f"[recording] reason: {exc}")
            print("[recording] manual ffmpeg command:")
            print(
                f"  ffmpeg -framerate {RECORD_FPS} -i "
                f"{self.record_frames_dir}/frame_%05d.png "
                f"-pix_fmt yuv420p {self.record_dir}/playback.mp4"
            )

    def _on_key(self, event):
        key = (event.key.name or "").upper()

        if key in ("W", "A", "S", "D", "UP", "DOWN", "LEFT", "RIGHT"):
            self.cam.on_key_press(event)
            return

        if key == "R":
            self.cam.set_state(self._cam_defaults)
            self.canvas.update()

        elif key == "SPACE":
            self.playing = not self.playing
            state = "playing" if self.playing else "paused"
            print(f"[animation] {state}")
            self._update_frame()
            self.canvas.update()

        elif key in ("+", "=", "PLUS"):
            self.speed += 1
            print(f"[speed] {self.speed} bar(s)/tick")
            self._update_frame()
            self.canvas.update()

        elif key in ("-", "_", "MINUS"):
            self.speed = max(1, self.speed - 1)
            print(f"[speed] {self.speed} bar(s)/tick")
            self._update_frame()
            self.canvas.update()

        elif key == "V":
            self._toggle_recording()
            self._update_frame()
            self.canvas.update()

        elif key == "S" and "Shift" in [m.name for m in (event.modifiers or [])]:
            filename = f"garch_{self.ticker}_{datetime.now():%Y%m%d_%H%M%S}.png"
            self._save_canvas_png(filename)
            print(f"[screenshot] -> {filename}")

        elif key in ("Q", "ESCAPE"):
            if self.recording:
                self._stop_recording()
            self.canvas.close()
            app.quit()


# -------------------------
# ENTRY POINTS
# -------------------------
def run(price_series: pd.Series, ticker: str = "SPY") -> None:
    df = compute_garch_metrics(price_series)

    # Keep a strong reference alive so Python does not garbage-collect
    # the visualizer and its timer while the VisPy window is open.
    viz = GarchFieldVisualizer(df, ticker=ticker)
    app.run()

    return viz


def run_from_df(df: pd.DataFrame, ticker: str = "CUSTOM") -> None:
    # Keep a strong reference alive so Python does not garbage-collect
    # the visualizer and its timer while the VisPy window is open.
    viz = GarchFieldVisualizer(df, ticker=ticker)
    app.run()

    return viz


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "SPY"

    print(f"Downloading {ticker} (2 years)...")

    raw = yf.download(ticker, period="2y", progress=False)

    if raw.empty:
        sys.exit(f"No data returned for '{ticker}'.")

    run(raw["Close"], ticker=ticker)
