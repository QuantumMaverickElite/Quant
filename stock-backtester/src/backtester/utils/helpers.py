import pandas as pd
from typing import Optional


def make_index_naive(idx: pd.Index) -> pd.Index:
    idx = pd.to_datetime(idx)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    return idx


def get_trading_day_index(price_df: pd.DataFrame, target_date: pd.Timestamp) -> Optional[int]:
    idx = price_df.index

    if target_date in idx:
        return idx.get_loc(target_date)

    later = idx[idx > target_date]
    if len(later) == 0:
        return None

    return idx.get_loc(later[0])
