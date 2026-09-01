# GARCH Volatility Surface Visualizer

This module contains an experimental 3D volatility visualization tool for the stock backtesting system.

The visualizer downloads historical market data, computes GARCH-based volatility metrics, builds a 3D volatility surface, and animates the surface forward through time. The animation is designed to show how volatility regimes, spikes, and regime transitions evolve across the time axis.

## Demo

Recorded examples are generated under output recording directories and are not
source-controlled documentation dependencies. Generate a local recording with
the demo command below instead of relying on a historical output path.

## File

`src/backtester/visuals/garch_state.py`

## What It Shows

The visualizer represents volatility as a 3D surface:

- X-axis: time
- Y-axis: volatility z-score regime axis
- Z-axis: annualized GARCH volatility

The animation reveals the surface over time instead of displaying the entire surface immediately. This makes it easier to see volatility clusters, regime changes, and spikes as they form.

## Core Logic

The visualizer follows this structure:

1. Download price data
2. Compute volatility metrics
3. Build the full GARCH volatility surface
4. Animate the surface forward through time
5. Update HUD metrics and playback cursor
6. Optionally record the animation

The current version uses a stable alpha-reveal method:

- Build the full mesh once
- Keep vertices and faces fixed
- Animate by changing vertex alpha values
- Avoid rebuilding the mesh every frame

This is safer and faster than repeatedly recreating the surface during playback.

## Controls

- LMB drag: orbit
- RMB drag: pan
- Scroll: zoom
- W/S or Up/Down: tilt elevation
- A/D or Left/Right: rotate azimuth
- R: reset camera
- Space: pause / play animation
- '+' / =: increase animation speed
- '-' / \_: decrease animation speed
- V: start / stop recording
- Shift+S: screenshot
- Q / Esc: quit

## Installation

From the project root:

`pip install -r requirements.txt`

The visualizer depends mainly on:

- numpy
- pandas
- scipy
- yfinance
- vispy
- PyQt6
- imageio
- imageio-ffmpeg

## Running the Visualizer

From the project root:

`python src/backtester/visuals/garch_state.py NVDA`

Other examples:

`python src/backtester/visuals/garch_state.py SPY`

`python src/backtester/visuals/garch_state.py TSLA`

`python src/backtester/visuals/garch_state.py QQQ`

## Recording

Press `V` while the visualizer is running to start recording. Press `V` again to stop.

Recordings are saved under:

`outputs/garch_recordings/<ticker>_<timestamp>/`

Each recording may contain:

- frames/
- playback.mp4
- playback.gif

The raw `frames/` directory can become very large and should usually remain ignored by Git.

## Notes

This visualizer is experimental research infrastructure. It is intended for studying volatility behavior and creating portfolio demonstrations. It is not financial advice and should not be treated as a trading signal by itself.
