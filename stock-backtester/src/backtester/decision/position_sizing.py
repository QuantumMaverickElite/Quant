from __future__ import annotations

import pandas as pd


def apply_route_risk_scaling(
    positions: pd.Series,
    routes: pd.DataFrame,
    multiplier_col: str = "route_risk_multiplier",
) -> pd.Series:
    """
    Scale strategy positions using the regime router's risk multiplier.

    Example:
        base position = 1.00
        route risk multiplier = 0.70
        final position = 0.70

    This does not change the strategy's direction.
    It only scales exposure.
    """

    if multiplier_col not in routes.columns:
        raise KeyError(f"Missing required route column: {multiplier_col}")

    aligned_multiplier = (
        routes[multiplier_col].reindex(positions.index).ffill().fillna(1.0)
    )

    scaled = positions.astype(float) * aligned_multiplier.astype(float)
    scaled.name = "route_scaled_position"

    return scaled
