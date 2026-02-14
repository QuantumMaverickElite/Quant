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

    # shift 1 day to avoid trading same day as signal
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

    # 50-day momentum (return over lookback)
    mom = close / close.shift(lookback) - 1.0

    # Daily returns for streak detection
    rets = close.pct_change()

    pos = pd.Series(0, index=close.index, dtype=int)
    in_pos = 0
    down_streak = 0
    up_streak = 0

    for i in range(1, len(close)):
        # If momentum is positive -> force hold long
        if pd.notna(mom.iloc[i]) and mom.iloc[i] > 0:
            in_pos = 1
            down_streak = 0
            up_streak = 0
            pos.iloc[i] = in_pos
            continue

        # Momentum not positive -> run streak logic
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

    # Shift 1 day to avoid trading on same close used to compute streak/momentum
    return pos.shift(1).fillna(0).astype(int)

