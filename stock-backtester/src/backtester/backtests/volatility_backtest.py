import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
import os

from backtester.strategies.options_strategies import volatility_options_decision

TICKER = "AAPL"
if len(sys.argv) > 1:
    TICKER = sys.argv[1]

START_DATE = "2020-01-01"

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

OUTPUT_PLOT = f"outputs/volatility/{TICKER}_backtest.png"


def compute_returns_and_vol(prices: pd.Series) -> pd.DataFrame:
    prices = prices.squeeze().dropna().astype(float)

    log_return = np.log(prices / prices.shift(1))
    fast_vol = log_return.rolling(FAST_VOL_WINDOW).std() * np.sqrt(252)
    slow_iv_proxy = log_return.rolling(SLOW_IV_PROXY_WINDOW).std() * np.sqrt(252)
    regime_mean = fast_vol.rolling(REGIME_WINDOW).mean()

    df = pd.DataFrame(index=prices.index)
    df["price"] = prices
    df["log_return"] = log_return
    df["fast_vol"] = fast_vol
    df["slow_iv_proxy"] = slow_iv_proxy
    df["regime_mean"] = regime_mean
    return df


def build_state(current_vol: float, regime_mean: float) -> dict:
    if pd.isna(current_vol) or pd.isna(regime_mean) or regime_mean <= 0:
        return {
            "is_high_vol": False,
            "is_spiking": False,
            "regime": "NORMAL",
            "vol": float(current_vol) if pd.notna(current_vol) else np.nan,
            "vol_percentile": 0.5,
            "vol_zscore": 0.0,
        }

    is_high_vol = current_vol > (regime_mean * HIGH_VOL_MULTIPLIER)
    is_spiking = current_vol > (regime_mean * SPIKE_MULTIPLIER)
    regime = "HIGH" if is_high_vol else "NORMAL"

    return {
        "is_high_vol": bool(is_high_vol),
        "is_spiking": bool(is_spiking),
        "regime": regime,
        "vol": float(current_vol),
        "vol_percentile": 0.5,
        "vol_zscore": 0.0,
    }


def simulate_trade_pnl(
    returns_window: pd.Series,
    signal: str,
    premium_cost: float,
    move_sensitivity: float,
    hold_days: int,
) -> float:
    """
    Harsher path-based PnL proxy.

    - Gains only partially track absolute movement
    - Theta-like decay every day
    - Additional entry friction
    """
    pnl = 0.0
    daily_theta = premium_cost / hold_days
    entry_slippage = 0.005

    if signal == "STRADDLE":
        multiplier = 1.0
    elif signal == "STRANGLE":
        multiplier = STRANGLE_HAIRCUT
    else:
        return 0.0

    pnl -= entry_slippage

    for daily_ret in returns_window:
        daily_move = abs(float(daily_ret))
        pnl += multiplier * move_sensitivity * daily_move
        pnl -= daily_theta

    # cap maximum loss roughly at premium + slippage
    pnl = max(pnl, -(premium_cost + entry_slippage))
    return float(pnl)


def compute_stats(r: pd.Series) -> dict:
    r = pd.to_numeric(r, errors="coerce").fillna(0.0)

    total_return = float((1.0 + r).prod() - 1.0)

    sharpe = 0.0
    std = float(r.std())
    if std > 0:
        sharpe = float((r.mean() / std) * np.sqrt(252))

    equity = (1.0 + r).cumprod()
    drawdown = equity / equity.cummax() - 1.0

    return {
        "total_return": total_return,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
    }


def main() -> None:
    price_data = yf.download(TICKER, start=START_DATE, auto_adjust=True, progress=False)
    if price_data.empty:
        raise RuntimeError(f"No price data downloaded for {TICKER}")

    prices = price_data["Close"].squeeze()
    df = compute_returns_and_vol(prices)
    df = df.dropna().copy()

    strategy_returns = np.zeros(len(df), dtype=float)
    signals = np.array(["NO_TRADE"] * len(df), dtype=object)

    i = 0
    n = len(df)

    while i < n:
        row = df.iloc[i]

        current_vol = float(row["fast_vol"])
        iv_proxy = float(row["slow_iv_proxy"])
        regime_mean = float(row["regime_mean"])

        vol_edge = current_vol - iv_proxy
        state = build_state(current_vol, regime_mean)

        signal = volatility_options_decision(state, vol_edge, threshold=EDGE_THRESHOLD)
        signals[i] = signal

        if signal in ("STRADDLE", "STRANGLE"):
            end = min(i + HOLD_DAYS, n - 1)
            returns_window = df["log_return"].iloc[i : end + 1]

            pnl = simulate_trade_pnl(
                returns_window=returns_window,
                signal=signal,
                premium_cost=PREMIUM_COST,
                move_sensitivity=MOVE_SENSITIVITY,
                hold_days=HOLD_DAYS,
            )

            strategy_returns[i] = pnl

            for j in range(i + 1, end + 1):
                signals[j] = "HOLD"

            i = end + 1
        else:
            i += 1

    df["strategy_return"] = pd.Series(strategy_returns, index=df.index, dtype="float64")
    df["bh_return"] = df["log_return"].fillna(0.0).astype(float)

    df["strategy_equity"] = (1.0 + df["strategy_return"]).cumprod()
    df["bh_equity"] = (1.0 + df["bh_return"]).cumprod()

    plt.figure(figsize=(10, 6))
    plt.plot(df.index, df["strategy_equity"], label=f"{TICKER} Vol Strategy")
    plt.plot(df.index, df["bh_equity"], label=f"{TICKER} Buy & Hold")
    plt.legend()
    plt.title(f"{TICKER} Volatility Strategy vs Buy & Hold")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.tight_layout()
    os.makedirs("outputs/volatility", exist_ok=True)
    plt.savefig(OUTPUT_PLOT)

    print(f"Ticker: {TICKER}")
    print("Using dynamic slow-vol proxy as IV benchmark")
    print(f"Saved: {OUTPUT_PLOT}")
    print()
    print("Strategy:", compute_stats(df["strategy_return"]))
    print("Buy & Hold:", compute_stats(df["bh_return"]))


if __name__ == "__main__":
    main()
