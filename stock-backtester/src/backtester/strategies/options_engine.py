from backtester.analytics.volatility import compute_garch_metrics
from backtester.analytics.volatility_state import get_volatility_state
from backtester.strategies.options_strategies import volatility_options_decision


def get_options_signal(price_series, implied_vol=None):
    """
    Full pipeline with optional IV comparison
    """

    metrics = compute_garch_metrics(price_series)
    latest_row = metrics.iloc[-1]

    state = get_volatility_state(latest_row)

    garch_vol = float(latest_row["garch_vol_annualized"])

    vol_edge = None
    if implied_vol is not None:
        vol_edge = garch_vol - implied_vol

    decision = volatility_options_decision(state, vol_edge)

    return {
        "decision": decision,
        "state": state,
        "metrics": latest_row,
        "vol_edge": vol_edge,
    }
