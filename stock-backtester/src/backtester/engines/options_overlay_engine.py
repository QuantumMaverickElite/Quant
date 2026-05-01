from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtester.strategies.options_strategies import volatility_options_decision

FAST_VOL_WINDOW = 20
SLOW_IV_PROXY_WINDOW = 60
REGIME_WINDOW = 100

EDGE_THRESHOLD = 0.05
HIGH_VOL_MULTIPLIER = 1.10
SPIKE_MULTIPLIER = 1.35

HOLD_DAYS = 5
PREMIUM_COST = 0.03
MOVE_SENSITIVITY = 0.35
STRANGLE_HAIRCUT = 0.60


@dataclass(frozen=True)
class OptionsOverlayConfig:
    fast_vol_window: int = FAST_VOL_WINDOW
    slow_iv_proxy_window: int = SLOW_IV_PROXY_WINDOW
    regime_window: int = REGIME_WINDOW
    edge_threshold: float = EDGE_THRESHOLD
    high_vol_multiplier: float = HIGH_VOL_MULTIPLIER
    spike_multiplier: float = SPIKE_MULTIPLIER
    hold_days: int = HOLD_DAYS
    premium_cost: float = PREMIUM_COST
    move_sensitivity: float = MOVE_SENSITIVITY
    strangle_haircut: float = STRANGLE_HAIRCUT
    capital_fraction: float = 0.10


@dataclass(frozen=True)
class OptionsOverlayResult:
    returns: pd.Series
    equity: pd.Series
    signals: pd.Series
    diagnostics: pd.DataFrame


def compute_overlay_vol_features(
    prices: pd.Series,
    config: OptionsOverlayConfig = OptionsOverlayConfig(),
) -> pd.DataFrame:
    prices = prices.squeeze().dropna().astype(float)

    log_return = np.log(prices / prices.shift(1))
    fast_vol = log_return.rolling(config.fast_vol_window).std() * np.sqrt(252)
    slow_iv_proxy = log_return.rolling(config.slow_iv_proxy_window).std() * np.sqrt(252)
    regime_mean = fast_vol.rolling(config.regime_window).mean()

    df = pd.DataFrame(index=prices.index)
    df["price"] = prices
    df["log_return"] = log_return
    df["fast_vol"] = fast_vol
    df["slow_iv_proxy"] = slow_iv_proxy
    df["regime_mean"] = regime_mean

    return df


def build_overlay_state(
    current_vol: float,
    regime_mean: float,
    config: OptionsOverlayConfig = OptionsOverlayConfig(),
) -> dict:
    if pd.isna(current_vol) or pd.isna(regime_mean) or regime_mean <= 0:
        return {
            "is_high_vol": False,
            "is_spiking": False,
            "regime": "NORMAL",
            "vol": float(current_vol) if pd.notna(current_vol) else np.nan,
            "vol_percentile": 0.5,
            "vol_zscore": 0.0,
        }

    is_high_vol = current_vol > (regime_mean * config.high_vol_multiplier)
    is_spiking = current_vol > (regime_mean * config.spike_multiplier)
    regime = "HIGH" if is_high_vol else "NORMAL"

    return {
        "is_high_vol": bool(is_high_vol),
        "is_spiking": bool(is_spiking),
        "regime": regime,
        "vol": float(current_vol),
        "vol_percentile": 0.5,
        "vol_zscore": 0.0,
    }


def simulate_options_trade_pnl(
    returns_window: pd.Series,
    signal: str,
    config: OptionsOverlayConfig = OptionsOverlayConfig(),
) -> float:
    pnl = 0.0
    daily_theta = config.premium_cost / config.hold_days
    entry_slippage = 0.005

    if signal == "STRADDLE":
        multiplier = 1.0
    elif signal == "STRANGLE":
        multiplier = config.strangle_haircut
    else:
        return 0.0

    pnl -= entry_slippage

    for daily_ret in returns_window:
        daily_move = abs(float(daily_ret))
        pnl += multiplier * config.move_sensitivity * daily_move
        pnl -= daily_theta

    pnl = max(pnl, -(config.premium_cost + entry_slippage))
    return float(pnl)


def run_options_overlay(
    prices: pd.Series,
    routes: pd.DataFrame | None = None,
    config: OptionsOverlayConfig = OptionsOverlayConfig(),
) -> OptionsOverlayResult:
    """
    Run a simplified long-vol options overlay.

    If routes are provided, options trades are only allowed when
    route_allow_options is True.
    """

    df = compute_overlay_vol_features(prices, config=config)
    df = df.dropna().copy()

    overlay_returns = np.zeros(len(df), dtype=float)
    signals = np.array(["NO_TRADE"] * len(df), dtype=object)

    if routes is not None:
        allow_options = (
            routes["route_allow_options"]
            .reindex(df.index)
            .ffill()
            .fillna(False)
            .astype(bool)
        )
    else:
        allow_options = pd.Series(True, index=df.index, dtype=bool)

    i = 0
    n = len(df)

    while i < n:
        row = df.iloc[i]
        date = df.index[i]

        if not bool(allow_options.loc[date]):
            i += 1
            continue

        current_vol = float(row["fast_vol"])
        iv_proxy = float(row["slow_iv_proxy"])
        regime_mean = float(row["regime_mean"])

        vol_edge = current_vol - iv_proxy
        state = build_overlay_state(current_vol, regime_mean, config=config)

        signal = volatility_options_decision(
            state,
            vol_edge,
            threshold=config.edge_threshold,
        )

        signals[i] = signal

        if signal in ("STRADDLE", "STRANGLE"):
            end = min(i + config.hold_days, n - 1)
            returns_window = df["log_return"].iloc[i : end + 1]

            pnl = simulate_options_trade_pnl(
                returns_window=returns_window,
                signal=signal,
                config=config,
            )

            overlay_returns[i] = pnl * config.capital_fraction

            for j in range(i + 1, end + 1):
                signals[j] = "HOLD"

            i = end + 1
        else:
            i += 1

    returns = pd.Series(overlay_returns, index=df.index, name="options_overlay_return")
    equity = (1.0 + returns).cumprod()
    equity.name = "options_overlay_equity"

    df["options_signal"] = pd.Series(signals, index=df.index, dtype="object")
    df["options_overlay_return"] = returns
    df["options_overlay_equity"] = equity

    return OptionsOverlayResult(
        returns=returns,
        equity=equity,
        signals=df["options_signal"],
        diagnostics=df,
    )
