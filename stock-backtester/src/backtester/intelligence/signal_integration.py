from __future__ import annotations

from pathlib import Path

import pandas as pd

from .candidates import action_label, detect_column, detect_date_column, detect_ticker_column, read_table, write_table


CONFIDENCE_COLUMNS = [
    "adjusted_confidence",
    "confidence",
    "signal_confidence",
    "score",
    "signal_score",
]


def latest_intelligence_features(features_csv: str | Path) -> pd.DataFrame:
    features = pd.read_csv(features_csv)
    if features.empty:
        return features
    if "query" not in features.columns:
        raise ValueError("Intelligence features CSV must contain a query column.")
    if "as_of" in features.columns:
        features["_as_of_sort"] = pd.to_datetime(features["as_of"], errors="coerce")
        features = features.sort_values("_as_of_sort").drop(columns=["_as_of_sort"])
    return features.drop_duplicates("query", keep="last")


def confidence_multiplier(regime_break_score: float, *, penalty_strength: float, min_multiplier: float) -> float:
    if pd.isna(regime_break_score):
        return 1.0
    return max(min_multiplier, 1.0 - penalty_strength * float(regime_break_score))


def latest_date_mask(df: pd.DataFrame, date_col: str | None = None) -> pd.Series:
    detected = detect_date_column(df, date_col)
    if not detected:
        raise ValueError("Could not detect date column for latest-date filtering.")
    dates = pd.to_datetime(df[detected], errors="coerce")
    latest = dates.max()
    if pd.isna(latest):
        raise ValueError(f"Could not parse any usable dates from column: {detected}")
    return dates.eq(latest)


def integrate_intelligence_features(
    *,
    signals_path: str | Path,
    features_csv: str | Path,
    out_path: str | Path,
    ticker_col: str | None = None,
    confidence_col: str | None = None,
    penalty_strength: float = 0.75,
    min_multiplier: float = 0.35,
    date_col: str | None = None,
    latest_date_only: bool = False,
) -> pd.DataFrame:
    signals = read_table(signals_path)
    ticker = detect_ticker_column(signals, ticker_col)
    confidence = confidence_col or detect_column(signals, CONFIDENCE_COLUMNS)
    active_mask = latest_date_mask(signals, date_col) if latest_date_only else pd.Series(True, index=signals.index)

    features = latest_intelligence_features(features_csv)
    if features.empty:
        out = signals.copy()
        out["intelligence_missing"] = active_mask
        write_table(out, out_path)
        return out

    features = features.copy()
    features["query"] = features["query"].astype(str).str.upper()
    rename = {}
    if "confidence" in features.columns:
        rename["confidence"] = "intelligence_confidence"
    features = features.rename(columns=rename)

    base = signals.copy()
    active = base.loc[active_mask].copy()
    inactive = base.loc[~active_mask].copy()

    active["_intelligence_query"] = active[ticker].astype(str).str.upper()
    active = active.merge(features, left_on="_intelligence_query", right_on="query", how="left", suffixes=("", "_intelligence"))
    active["intelligence_missing"] = active["regime_break_score"].isna()
    active["intelligence_action_label"] = active["regime_break_score"].fillna(0.0).map(action_label)
    active.loc[active["intelligence_missing"], "intelligence_action_label"] = "intelligence_missing_not_evaluated"
    active["intelligence_confidence_multiplier"] = active["regime_break_score"].map(
        lambda score: confidence_multiplier(score, penalty_strength=penalty_strength, min_multiplier=min_multiplier)
    )

    inactive["intelligence_missing"] = True
    inactive["intelligence_action_label"] = "not_evaluated_historical_row"
    inactive["intelligence_confidence_multiplier"] = 1.0

    if confidence:
        active[f"{confidence}_pre_intelligence"] = active[confidence]
        active[f"{confidence}_intelligence_adjusted"] = active[confidence] * active["intelligence_confidence_multiplier"]
        inactive[f"{confidence}_pre_intelligence"] = inactive[confidence]
        inactive[f"{confidence}_intelligence_adjusted"] = inactive[confidence]

    active = active.drop(columns=["_intelligence_query"])
    out = pd.concat([inactive, active], ignore_index=True, sort=False).sort_index(kind="stable")
    write_table(out, out_path)
    return out
