import pandas as pd

def sma_crossover(close: pd.Series, fast: int, slow: int) -> pd.Series:
    if fast >= slow:
        raise ValueError("fast must be < slow")

    sma_fast = close.rolling(fast).mean()
    sma_slow = close.rolling(slow).mean()

    signal = (sma_fast > sma_slow).astype(int)
    return signal.shift(1).fillna(0).astype(int)


def rsi_mean_reversion_positions(
    close: pd.Series,
    period: int = 14,
    buy_below: float = 30,
    sell_above: float = 70,
) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    pos = pd.Series(0, index=close.index, dtype=int)
    in_pos = 0

    for i in range(1, len(close)):
        if pd.isna(rsi.iloc[i]):
            pos.iloc[i] = in_pos
            continue

        if in_pos == 0 and rsi.iloc[i] < buy_below:
            in_pos = 1
        elif in_pos == 1 and rsi.iloc[i] > sell_above:
            in_pos = 0

        pos.iloc[i] = in_pos

    return pos.shift(1).fillna(0).astype(int)


def consecutive_reversal_positions(
    close: pd.Series,
    down_days: int = 2,
    up_days: int = 1,
) -> pd.Series:
    """
    Mean-reversion strategy:
    - Enter long after `down_days` consecutive negative returns.
    - Exit after `up_days` consecutive positive returns.
    """

    returns = close.pct_change()

    pos = pd.Series(0, index=close.index, dtype=int)
    in_pos = 0

    down_streak = 0
    up_streak = 0

    for i in range(1, len(close)):
        r = returns.iloc[i]

        if pd.isna(r):
            pos.iloc[i] = in_pos
            continue

        if r < 0:
            down_streak += 1
            up_streak = 0
        elif r > 0:
            up_streak += 1
            down_streak = 0
        else:
            down_streak = 0
            up_streak = 0

        if in_pos == 0 and down_streak >= down_days:
            in_pos = 1
        elif in_pos == 1 and up_streak >= up_days:
            in_pos = 0

        pos.iloc[i] = in_pos

    return pos.shift(1).fillna(0).astype(int)


def momentum50_else_streak_positions(
    close: pd.Series,
    lookback: int = 50,
    down_days: int = 2,
    up_days: int = 1,
) -> pd.Series:
    """
    Regime filter:
      - If 50-day return > 0: hold long (position=1), ignore streak logic.
      - Else: use streak mean-reversion:
          * enter after `down_days` consecutive down days
          * exit after `up_days` consecutive up days
    """

    mom = close / close.shift(lookback) - 1.0
    rets = close.pct_change()

    pos = pd.Series(0, index=close.index, dtype=int)
    in_pos = 0
    down_streak = 0
    up_streak = 0

    for i in range(1, len(close)):
        if pd.notna(mom.iloc[i]) and mom.iloc[i] > 0:
            in_pos = 1
            down_streak = 0
            up_streak = 0
            pos.iloc[i] = in_pos
            continue

        r = rets.iloc[i]
        if pd.isna(r):
            pos.iloc[i] = in_pos
            continue

        if r < 0:
            down_streak += 1
            up_streak = 0
        elif r > 0:
            up_streak += 1
            down_streak = 0
        else:
            down_streak = 0
            up_streak = 0

        if in_pos == 0 and down_streak >= down_days:
            in_pos = 1
        elif in_pos == 1 and up_streak >= up_days:
            in_pos = 0

        pos.iloc[i] = in_pos

    return pos.shift(1).fillna(0).astype(int)
def regime_positions(
    close: pd.Series,
    lookback: int,
    down_days: int,
    up_days: int,
    crash_week_drop: float,
    crash_hold_days: int,
    crash_down_days: int,
    crash_up_days: int,
    down_leverage: float,
    disable_leverage_in_crash: bool = True,
) -> pd.Series:
    """
    Multi-regime strategy:

    1) Momentum override:
       - mom(t) = close(t)/close(t-lookback) - 1
       - if mom(t) > 0 -> hold long (exposure = 1.0)

    2) Otherwise (mom <= 0):
       - run streak mean-reversion:
         * enter long after `down_days` consecutive down days
         * exit to cash after `up_days` consecutive up days
       - when long, apply leverage in this regime: exposure = down_leverage (e.g. 1.3)

    3) Crash trigger:
       - week_ret(t) = close(t)/close(t-5) - 1
       - if week_ret(t) <= -crash_week_drop, then starting NEXT day, enable crash mode for `crash_hold_days` days
       - during crash mode:
         * ignore momentum override (no forced holding)
         * use faster streak params (crash_down_days / crash_up_days)
         * optionally disable leverage (default True) to avoid levering into panic

    We shift the final exposure series by 1 day to avoid lookahead.
    """

    mom = close / close.shift(lookback) - 1.0
    rets = close.pct_change()

    week_ret = close / close.shift(5) - 1.0
    crash_trigger_next = (week_ret <= -crash_week_drop).shift(1).fillna(False)
    crash_active = crash_trigger_next.rolling(crash_hold_days).max().fillna(0).astype(bool)

    exposure = pd.Series(0.0, index=close.index, dtype=float)

    in_pos = 0
    down_streak = 0
    up_streak = 0

    for i in range(1, len(close)):
        in_crash = bool(crash_active.iloc[i])
        mom_is_pos = pd.notna(mom.iloc[i]) and mom.iloc[i] > 0

        if (not in_crash) and mom_is_pos:
            in_pos = 1
            down_streak = 0
            up_streak = 0
            exposure.iloc[i] = 1.0
            continue

        dd = crash_down_days if in_crash else down_days
        ud = crash_up_days if in_crash else up_days

        r = rets.iloc[i]
        if pd.isna(r):
            lev = 1.0
            if not mom_is_pos:
                lev = float(down_leverage)
                if disable_leverage_in_crash and in_crash:
                    lev = 1.0
            exposure.iloc[i] = lev * in_pos
            continue

        if r < 0:
            down_streak += 1
            up_streak = 0
        elif r > 0:
            up_streak += 1
            down_streak = 0
        else:
            down_streak = 0
            up_streak = 0

        if in_pos == 0 and down_streak >= dd:
            in_pos = 1
        elif in_pos == 1 and up_streak >= ud:
            in_pos = 0

        lev = 1.0
        if not mom_is_pos:
            lev = float(down_leverage)
            if disable_leverage_in_crash and in_crash:
                lev = 1.0

        exposure.iloc[i] = lev * in_pos

    return exposure.shift(1).fillna(0.0).astype(float)
