from __future__ import annotations

from pathlib import Path

import pandas as pd

from .candidates import read_table, write_table
from .opportunity_scorer import add_opportunity_scores


ACTION_POSITION_SCALE = {
    "same_regime_scale_in_allowed": 1.00,
    "caution_hold_no_adding": 0.65,
    "likely_regime_damage_do_not_average_down": 0.25,
    "thesis_break_risk_reduce_or_wait": 0.00,
    "not_evaluated_historical_row": 1.00,
}


def position_scale_from_score(score: float) -> float:
    if pd.isna(score):
        return 1.0
    score = float(score)
    if score < 0.30:
        return 1.0
    if score < 0.55:
        return 0.65
    if score < 0.75:
        return 0.25
    return 0.0


OPPORTUNITY_FEATURE_COLUMNS = [
    "contextual_event_risk",
    "mean_event_signed_impact",
    "macro_event_pressure",
    "sector_event_pressure",
    "ticker_event_pressure",
    "peer_event_pressure",
    "index_event_pressure",
    "rates_event_pressure",
    "inflation_event_pressure",
    "valuation_event_pressure",
    "liquidity_event_pressure",
    "guidance_event_pressure",
    "earnings_event_pressure",
    "fundamental_event_pressure",
    "sector_rotation_event_pressure",
    "commodity_event_pressure",
    "political_event_pressure",
    "geopolitical_event_pressure",
    "legal_event_pressure",
    "event_count",
    "event_cluster_count",
    "event_opportunity_score",
    "event_downside_risk_score",
    "event_opportunity_multiplier",
    "event_downside_multiplier",
    "net_event_multiplier",
    "net_event_score",
]


def merge_opportunity_features(
    signals: pd.DataFrame,
    *,
    opportunity_features_csv: str | Path,
    ticker_col: str = "ticker",
) -> pd.DataFrame:
    """Merge contextual event/opportunity features into a signal table by ticker."""
    if ticker_col not in signals.columns:
        raise ValueError(f"Ticker column not found: {ticker_col}")

    features = pd.read_csv(opportunity_features_csv)
    if "query" not in features.columns:
        raise ValueError("Opportunity feature CSV must contain a query column")

    features = features.copy()
    features["__ticker_key"] = features["query"].astype(str).str.upper()
    if "as_of" in features.columns:
        features = features.sort_values("as_of")
    features = features.drop_duplicates("__ticker_key", keep="last")

    keep_cols = ["__ticker_key"] + [col for col in OPPORTUNITY_FEATURE_COLUMNS if col in features.columns]
    features = features[keep_cols]

    out = signals.copy()
    out["__ticker_key"] = out[ticker_col].astype(str).str.upper()

    # Feature CSV values are more recent/richer than columns previously attached to
    # the signal table, so replace overlapping opportunity columns intentionally.
    replace_cols = [col for col in keep_cols if col != "__ticker_key" and col in out.columns]
    if replace_cols:
        out = out.drop(columns=replace_cols)

    out = out.merge(features, on="__ticker_key", how="left")
    return out.drop(columns=["__ticker_key"])


def build_allocator_ready_signals(
    *,
    signals_path: str | Path,
    out_path: str | Path,
    confidence_col: str = "adjusted_confidence",
    latest_date_only: bool = True,
    apply_event_opportunity: bool = True,
    opportunity_features_csv: str | Path | None = None,
    ticker_col: str = "ticker",
) -> pd.DataFrame:
    df = read_table(signals_path)
    if confidence_col not in df.columns:
        raise ValueError(f"Confidence column not found: {confidence_col}")

    out = df.copy()
    if "regime_break_score" in out.columns:
        out["intelligence_position_scale"] = out["regime_break_score"].map(position_scale_from_score)
    elif "intelligence_action_label" in out.columns:
        out["intelligence_position_scale"] = out["intelligence_action_label"].map(ACTION_POSITION_SCALE).fillna(1.0)
    else:
        out["intelligence_position_scale"] = 1.0

    if latest_date_only and "intelligence_action_label" in out.columns:
        historical = out["intelligence_action_label"].eq("not_evaluated_historical_row")
        out.loc[historical, "intelligence_position_scale"] = 1.0

    if opportunity_features_csv is not None:
        out = merge_opportunity_features(
            out,
            opportunity_features_csv=opportunity_features_csv,
            ticker_col=ticker_col,
        )

    if apply_event_opportunity:
        out = add_opportunity_scores(out)
    else:
        out["event_opportunity_multiplier"] = 1.0
        out["event_downside_multiplier"] = 1.0
        out["net_event_multiplier"] = 1.0

    adjusted_col = f"{confidence_col}_intelligence_adjusted"
    if adjusted_col in out.columns:
        base_adjusted = out[adjusted_col]
    else:
        base_adjusted = out[confidence_col] * out["intelligence_position_scale"]

    out["allocator_confidence_intelligence_adjusted"] = (
        base_adjusted * out["net_event_multiplier"].fillna(1.0)
    )

    if latest_date_only and "intelligence_action_label" in out.columns:
        historical = out["intelligence_action_label"].eq("not_evaluated_historical_row")
        out.loc[historical, "event_opportunity_multiplier"] = 1.0
        out.loc[historical, "event_downside_multiplier"] = 1.0
        out.loc[historical, "net_event_multiplier"] = 1.0
        out.loc[historical, "allocator_confidence_intelligence_adjusted"] = out.loc[
            historical, confidence_col
        ]

    out["allocator_confidence_pre_intelligence"] = out[confidence_col]
    out["allocator_confidence_delta"] = (
        out["allocator_confidence_intelligence_adjusted"] - out["allocator_confidence_pre_intelligence"]
    )
    out["allocator_intelligence_enabled"] = True

    write_table(out, out_path)
    return out
