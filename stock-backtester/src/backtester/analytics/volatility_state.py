def get_volatility_state(row):
    return {
        "is_high_vol": bool(row["vol_high_flag"]),
        "is_spiking": bool(row["vol_spike_flag"]),
        "regime": row["vol_regime"],
        "vol": float(row["garch_vol"]),
        "vol_percentile": float(row["vol_percentile"]),
        "vol_zscore": (
            float(row["vol_zscore"]) if row["vol_zscore"] == row["vol_zscore"] else None
        ),
    }
