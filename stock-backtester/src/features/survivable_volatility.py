from __future__ import annotations

import numpy as np
import pandas as pd


def assign_market_cap_tier(market_cap: pd.Series) -> pd.Series:
    """
    Assign market-cap tiers.

    Tiers:
    0 = micro/small/fragile
    1 = mid/normal
    2 = large
    3 = major large-cap
    4 = mega-cap
    5 = ultra mega-cap
    """

    cap = pd.to_numeric(market_cap, errors="coerce")

    conditions = [
        cap < 25e9,
        (cap >= 25e9) & (cap < 100e9),
        (cap >= 100e9) & (cap < 250e9),
        (cap >= 250e9) & (cap < 500e9),
        (cap >= 500e9) & (cap < 1e12),
        cap >= 1e12,
    ]

    choices = [0, 1, 2, 3, 4, 5]

    return pd.Series(
        np.select(conditions, choices, default=np.nan),
        index=market_cap.index,
        dtype="float64",
    )


def cap_tolerance_multiplier(market_cap_tier: pd.Series) -> pd.Series:
    """
    Convert market-cap tier into volatility tolerance.

    Higher tier = more tolerance.
    Lower tier = less tolerance.
    """

    mapping = {
        0: 0.75,  # small/fragile: volatility is more dangerous
        1: 1.00,  # normal
        2: 1.15,  # $100B-$250B
        3: 1.30,  # $250B-$500B
        4: 1.50,  # $500B-$1T
        5: 1.75,  # $1T+
    }

    return market_cap_tier.map(mapping).fillna(1.0)


def trend_quality_score(df: pd.DataFrame) -> pd.Series:
    """
    Compute a simple price-only trend quality score.

    Optional columns:
    - close
    - sma_50
    - sma_200
    - distance_from_52w_high

    Returns:
    - score between 0 and 1

    Interpretation:
    - higher score = trend structure is healthier
    - lower score = trend structure is damaged
    """

    score = pd.Series(0.5, index=df.index, dtype="float64")

    if {"close", "sma_50"}.issubset(df.columns):
        score += np.where(df["close"] >= df["sma_50"], 0.15, -0.10)

    if {"close", "sma_200"}.issubset(df.columns):
        score += np.where(df["close"] >= df["sma_200"], 0.20, -0.20)

    if "distance_from_52w_high" in df.columns:
        dd = pd.to_numeric(df["distance_from_52w_high"], errors="coerce")

        # distance_from_52w_high should usually be negative or zero.
        # Example: -0.15 means 15% below the 52-week high.
        score += np.select(
            [
                dd >= -0.10,
                (dd < -0.10) & (dd >= -0.25),
                (dd < -0.25) & (dd >= -0.40),
                dd < -0.40,
            ],
            [
                0.15,
                0.05,
                -0.10,
                -0.25,
            ],
            default=0.0,
        )

    return score.clip(0.0, 1.0)


def compute_survivable_volatility(
    df: pd.DataFrame,
    *,
    market_cap_col: str = "market_cap",
    vol_z_col: str = "vol_z",
    drawdown_col: str = "drawdown",
    base_confidence_col: str | None = "confidence",
) -> pd.DataFrame:
    """
    Add Survivable Volatility Engine columns.

    Required:
    - market_cap

    Strongly recommended:
    - vol_z
    - drawdown
    - confidence

    Optional:
    - close
    - sma_50
    - sma_200
    - distance_from_52w_high

    Core idea:
    - high volatility creates pressure
    - larger companies receive more volatility tolerance
    - strong trend structure receives more tolerance
    - missing price structure does not receive free forgiveness
    """

    out = df.copy()

    if market_cap_col not in out.columns:
        raise ValueError(f"Missing required column: {market_cap_col}")

    if vol_z_col not in out.columns:
        out[vol_z_col] = 0.0

    if drawdown_col not in out.columns:
        out[drawdown_col] = 0.0

    out["market_cap_tier"] = assign_market_cap_tier(out[market_cap_col])
    out["cap_tolerance_multiplier"] = cap_tolerance_multiplier(out["market_cap_tier"])

    vol_z = pd.to_numeric(out[vol_z_col], errors="coerce").fillna(0.0)
    drawdown = pd.to_numeric(out[drawdown_col], errors="coerce").fillna(0.0)

    # Convert drawdown to positive severity.
    # Example: -0.20 drawdown becomes 0.20 severity.
    drawdown_severity = drawdown.abs()

    # Raw volatility pressure.
    # Normal vol_z around 0 should not punish heavily.
    # vol_z above 1 starts to matter.
    out["vol_pressure_raw"] = np.maximum(vol_z, 0.0)

    # Drawdown pressure rises with drawdown severity.
    out["drawdown_pressure_raw"] = drawdown_severity

    out["exit_pressure_raw"] = (
        0.65 * out["vol_pressure_raw"] + 3.00 * out["drawdown_pressure_raw"]
    )

    out["trend_quality_score"] = trend_quality_score(out)

    price_feature_cols = [
        "close",
        "sma_50",
        "sma_200",
        "distance_from_52w_high",
    ]

    available_price_feature_cols = [
        col for col in price_feature_cols if col in out.columns
    ]

    if available_price_feature_cols:
        out["price_features_missing"] = (
            out[available_price_feature_cols].isna().any(axis=1)
        )
    else:
        out["price_features_missing"] = True

    # Missing price structure means we do not have proof that volatility is survivable.
    # Keep it neutral-to-cautious rather than rewarding it.
    out.loc[out["price_features_missing"], "trend_quality_score"] = 0.35

    # Strong trend gives additional tolerance.
    out["trend_tolerance_multiplier"] = 0.75 + out["trend_quality_score"]

    out["total_tolerance_multiplier"] = (
        out["cap_tolerance_multiplier"] * out["trend_tolerance_multiplier"]
    )

    out["exit_pressure_adjusted"] = (
        out["exit_pressure_raw"] / out["total_tolerance_multiplier"]
    )

    # Adjusted volatility penalty.
    # Larger / stronger companies get less punished for the same volatility.
    out["vol_penalty_adjusted"] = (
        out["vol_pressure_raw"] / out["total_tolerance_multiplier"]
    )

    # Survivable volatility score.
    # Higher means volatility is more acceptable.
    out["survivable_vol_score"] = (
        out["cap_tolerance_multiplier"] * 0.55 + out["trend_quality_score"] * 0.45
    ).clip(0.0, 2.0)

    # Position size permission.
    # If adjusted exit pressure is high, size gets reduced.
    out["size_permission_multiplier"] = np.select(
        [
            out["exit_pressure_adjusted"] < 0.75,
            (out["exit_pressure_adjusted"] >= 0.75)
            & (out["exit_pressure_adjusted"] < 1.50),
            (out["exit_pressure_adjusted"] >= 1.50)
            & (out["exit_pressure_adjusted"] < 2.50),
            out["exit_pressure_adjusted"] >= 2.50,
        ],
        [
            1.05,
            1.00,
            0.75,
            0.40,
        ],
        default=1.00,
    )

    # Missing price features should never receive a size boost.
    out.loc[out["price_features_missing"], "size_permission_multiplier"] = np.minimum(
        out.loc[out["price_features_missing"], "size_permission_multiplier"],
        1.00,
    )

    # Dip-buy permission:
    # Needs large enough cap, decent trend, and meaningful drawdown.
    out["dip_buy_permission"] = (
        (out["market_cap_tier"] >= 3)
        & (out["trend_quality_score"] >= 0.45)
        & (drawdown_severity >= 0.06)
        & (out["exit_pressure_adjusted"] < 2.25)
    )

    # Missing price structure should never receive dip-buy permission.
    out.loc[out["price_features_missing"], "dip_buy_permission"] = False

    # Optional confidence adjustment.
    if base_confidence_col is not None and base_confidence_col in out.columns:
        base_conf = pd.to_numeric(out[base_confidence_col], errors="coerce").fillna(0.0)

        # Penalize excessive adjusted volatility, but reward survivable volatility slightly.
        confidence_multiplier = out["size_permission_multiplier"] * (
            1.0 + 0.04 * (out["survivable_vol_score"] - 1.0)
        )

        out["confidence_survivable_vol_adjusted"] = (
            base_conf * confidence_multiplier
        ).clip(0.0, 1.0)

    return out
