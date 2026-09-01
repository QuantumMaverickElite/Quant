from __future__ import annotations

from pathlib import Path

import pandas as pd


POSITIVE_EVENT_FEATURES = [
    "ticker_event_pressure",
    "peer_event_pressure",
    "sector_event_pressure",
    "index_event_pressure",
    "macro_event_pressure",
    "rates_event_pressure",
    "inflation_event_pressure",
    "valuation_event_pressure",
    "liquidity_event_pressure",
    "guidance_event_pressure",
    "earnings_event_pressure",
    "fundamental_event_pressure",
    "sector_rotation_event_pressure",
    "commodity_event_pressure",
    "sentiment_score",
]

NEGATIVE_EVENT_FEATURES = [
    "ticker_event_pressure",
    "peer_event_pressure",
    "sector_event_pressure",
    "index_event_pressure",
    "macro_event_pressure",
    "rates_event_pressure",
    "inflation_event_pressure",
    "valuation_event_pressure",
    "liquidity_event_pressure",
    "guidance_event_pressure",
    "earnings_event_pressure",
    "fundamental_event_pressure",
    "sector_rotation_event_pressure",
    "political_event_pressure",
    "geopolitical_event_pressure",
    "legal_event_pressure",
    "sentiment_score",
]

OPPORTUNITY_WEIGHTS = {
    "ticker_event_pressure": 0.22,
    "fundamental_event_pressure": 0.18,
    "guidance_event_pressure": 0.16,
    "earnings_event_pressure": 0.12,
    "sector_event_pressure": 0.10,
    "peer_event_pressure": 0.08,
    "macro_event_pressure": 0.07,
    "rates_event_pressure": 0.06,
    "liquidity_event_pressure": 0.05,
    "valuation_event_pressure": 0.05,
    "sector_rotation_event_pressure": 0.05,
    "index_event_pressure": 0.04,
    "commodity_event_pressure": 0.04,
    "inflation_event_pressure": 0.03,
    "sentiment_score": 0.10,
}

RISK_WEIGHTS = {
    "ticker_event_pressure": 0.20,
    "legal_event_pressure": 0.18,
    "guidance_event_pressure": 0.16,
    "fundamental_event_pressure": 0.14,
    "macro_event_pressure": 0.12,
    "rates_event_pressure": 0.10,
    "sector_event_pressure": 0.10,
    "peer_event_pressure": 0.08,
    "valuation_event_pressure": 0.08,
    "political_event_pressure": 0.07,
    "geopolitical_event_pressure": 0.07,
    "liquidity_event_pressure": 0.06,
    "inflation_event_pressure": 0.06,
    "index_event_pressure": 0.05,
    "earnings_event_pressure": 0.05,
    "sentiment_score": 0.08,
}


def clamp01(x: float) -> float:
    if pd.isna(x):
        return 0.0
    return float(max(0.0, min(1.0, x)))


def positive_component(x: float) -> float:
    return clamp01(x)


def negative_component(x: float) -> float:
    return clamp01(-x)


def weighted_score(row: pd.Series, weights: dict[str, float], *, positive: bool) -> float:
    total_weight = 0.0
    total = 0.0
    for col, weight in weights.items():
        if col not in row.index:
            continue
        raw = row[col]
        component = positive_component(raw) if positive else negative_component(raw)
        total += weight * component
        total_weight += weight
    if total_weight <= 0:
        return 0.0
    return clamp01(total / total_weight)


def opportunity_multiplier(
    opportunity_score: float,
    *,
    max_boost: float = 0.25,
    min_opportunity_for_boost: float = 0.05,
) -> float:
    score = clamp01(opportunity_score)
    if score <= min_opportunity_for_boost:
        return 1.0
    scaled = (score - min_opportunity_for_boost) / max(1e-9, 1.0 - min_opportunity_for_boost)
    return round(1.0 + max_boost * scaled, 6)


def ranked_opportunity_multiplier(
    *,
    opportunity_score: float,
    opportunity_rank: float,
    max_boost: float = 0.12,
    min_opportunity_for_boost: float = 0.005,
    min_rank_for_boost: float = 0.70,
) -> float:
    """Boost unusually positive candidates within the current evaluated universe."""
    score = clamp01(opportunity_score)
    rank = clamp01(opportunity_rank)
    if score <= min_opportunity_for_boost or rank <= min_rank_for_boost:
        return 1.0
    scaled_rank = (rank - min_rank_for_boost) / max(1e-9, 1.0 - min_rank_for_boost)
    scaled_score = min(1.0, score / 0.05)
    return round(1.0 + max_boost * scaled_rank * scaled_score, 6)


def risk_multiplier(
    risk_score: float,
    *,
    max_penalty: float = 0.45,
) -> float:
    return round(max(0.0, 1.0 - max_penalty * clamp01(risk_score)), 6)


def ranked_risk_multiplier(
    *,
    risk_score: float,
    risk_rank: float,
    max_penalty: float = 0.20,
    min_risk_for_penalty: float = 0.003,
    min_rank_for_penalty: float = 0.70,
) -> float:
    """Apply a bounded extra penalty to unusually risky event profiles."""
    score = clamp01(risk_score)
    rank = clamp01(risk_rank)
    if score <= min_risk_for_penalty or rank <= min_rank_for_penalty:
        return 1.0
    scaled_rank = (rank - min_rank_for_penalty) / max(1e-9, 1.0 - min_rank_for_penalty)
    scaled_score = min(1.0, score / 0.05)
    return round(max(0.0, 1.0 - max_penalty * scaled_rank * scaled_score), 6)


def gate_opportunity_multiplier(
    opportunity_mult: float,
    *,
    regime_break_score: float | None,
    price_action_risk: float | None,
    intelligence_action_label: str | None,
) -> float:
    """Prevent positive news from boosting damaged setups."""
    regime = clamp01(regime_break_score or 0.0)
    price_risk = clamp01(price_action_risk or 0.0)
    label = intelligence_action_label or ""

    if label in {"thesis_break_risk_reduce_or_wait", "likely_regime_damage_do_not_average_down"}:
        return 1.0
    if label == "caution_hold_no_adding":
        return 1.0
    if regime >= 0.30 or price_risk >= 0.50:
        return 1.0
    return opportunity_mult


def add_opportunity_scores(
    df: pd.DataFrame,
    *,
    max_boost: float = 0.25,
    max_event_penalty: float = 0.45,
    use_cross_sectional_ranks: bool = True,
    max_rank_boost: float = 0.12,
    max_rank_penalty: float = 0.20,
) -> pd.DataFrame:
    out = df.copy()
    out["event_opportunity_score"] = out.apply(
        lambda row: weighted_score(row, OPPORTUNITY_WEIGHTS, positive=True),
        axis=1,
    )
    out["event_downside_risk_score"] = out.apply(
        lambda row: weighted_score(row, RISK_WEIGHTS, positive=False),
        axis=1,
    )
    out["event_opportunity_multiplier_raw"] = out["event_opportunity_score"].map(
        lambda score: opportunity_multiplier(score, max_boost=max_boost)
    )
    out["event_downside_multiplier"] = out["event_downside_risk_score"].map(
        lambda score: risk_multiplier(score, max_penalty=max_event_penalty)
    )

    if "intelligence_action_label" in out.columns:
        eligible = ~out["intelligence_action_label"].isin(
            ["not_evaluated_historical_row", "intelligence_missing_not_evaluated"]
        )
    else:
        eligible = pd.Series(True, index=out.index)

    out["event_opportunity_rank"] = 0.0
    out["event_downside_risk_rank"] = 0.0
    out.loc[eligible, "event_opportunity_rank"] = (
        out.loc[eligible, "event_opportunity_score"].rank(pct=True, method="average").fillna(0.0)
    )
    out.loc[eligible, "event_downside_risk_rank"] = (
        out.loc[eligible, "event_downside_risk_score"].rank(pct=True, method="average").fillna(0.0)
    )

    if use_cross_sectional_ranks:
        rank_boost = out.apply(
            lambda row: ranked_opportunity_multiplier(
                opportunity_score=row["event_opportunity_score"],
                opportunity_rank=row["event_opportunity_rank"],
                max_boost=max_rank_boost,
            ),
            axis=1,
        )
        rank_penalty = out.apply(
            lambda row: ranked_risk_multiplier(
                risk_score=row["event_downside_risk_score"],
                risk_rank=row["event_downside_risk_rank"],
                max_penalty=max_rank_penalty,
            ),
            axis=1,
        )
        out["event_opportunity_multiplier_raw"] = out[
            ["event_opportunity_multiplier_raw"]
        ].join(rank_boost.rename("rank_boost")).max(axis=1)
        out["event_downside_multiplier"] = out[
            ["event_downside_multiplier"]
        ].join(rank_penalty.rename("rank_penalty")).min(axis=1)

    out["event_opportunity_multiplier"] = out.apply(
        lambda row: gate_opportunity_multiplier(
            row["event_opportunity_multiplier_raw"],
            regime_break_score=row.get("regime_break_score"),
            price_action_risk=row.get("price_action_risk"),
            intelligence_action_label=row.get("intelligence_action_label"),
        ),
        axis=1,
    )
    out["net_event_multiplier"] = (
        out["event_opportunity_multiplier"] * out["event_downside_multiplier"]
    ).round(6)
    out["net_event_score"] = (
        out["event_opportunity_score"] - out["event_downside_risk_score"]
    ).round(6)
    return out


def add_opportunity_scores_to_csv(
    *,
    in_csv: str | Path,
    out_csv: str | Path,
    max_boost: float = 0.25,
    max_event_penalty: float = 0.45,
) -> pd.DataFrame:
    df = pd.read_csv(in_csv)
    out = add_opportunity_scores(df, max_boost=max_boost, max_event_penalty=max_event_penalty)
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    return out
