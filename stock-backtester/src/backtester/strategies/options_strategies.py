def volatility_options_decision(state, vol_edge=None, threshold=0.02):
    """
    Decide options strategy using volatility + IV edge
    """

    # Only trade if edge is meaningful
    if vol_edge is not None:
        if vol_edge > threshold:
            if state["is_spiking"] and state["is_high_vol"]:
                return "STRADDLE"

            if state["is_high_vol"]:
                return "STRANGLE"

        return "NO_TRADE"

    # Fallback (no IV)
    if state["is_spiking"] and state["is_high_vol"]:
        return "STRADDLE"

    if state["is_high_vol"]:
        return "STRANGLE"

    return "NO_TRADE"
