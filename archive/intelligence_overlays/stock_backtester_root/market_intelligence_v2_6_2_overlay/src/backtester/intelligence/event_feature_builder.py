from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


SCOPE_FEATURES = {
    "ticker": "ticker_event_pressure",
    "peer_group": "peer_event_pressure",
    "sector": "sector_event_pressure",
    "index": "index_event_pressure",
    "macro": "macro_event_pressure",
    "political": "political_event_pressure",
    "commodity": "commodity_event_pressure",
    "unknown": "unknown_event_pressure",
}

EVENT_TYPE_FEATURES = {
    "price_action": "price_action_event_pressure",
    "rates": "rates_event_pressure",
    "inflation": "inflation_event_pressure",
    "earnings": "earnings_event_pressure",
    "guidance": "guidance_event_pressure",
    "valuation": "valuation_event_pressure",
    "liquidity": "liquidity_event_pressure",
    "legal": "legal_event_pressure",
    "geopolitical": "geopolitical_event_pressure",
    "sector_rotation": "sector_rotation_event_pressure",
    "commodity": "commodity_event_pressure_by_type",
    "company_fundamental": "fundamental_event_pressure",
    "general_news": "general_event_pressure",
}


def clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    if pd.isna(x) or np.isinf(x):
        return 0.0
    return float(max(lo, min(hi, x)))


def clamp01(x: float) -> float:
    return clamp(x, 0.0, 1.0)


def signed_impact(row: pd.Series) -> float:
    direction = str(row.get("direction", "neutral")).lower()
    sign = 1.0 if direction == "bullish" else -1.0 if direction == "bearish" else 0.0
    if direction == "mixed":
        sign = 0.0
    magnitude = float(row.get("magnitude", 0.0) or 0.0)
    confidence = float(row.get("confidence", 0.0) or 0.0)
    novelty = float(row.get("novelty", 0.5) or 0.5)
    reliability = float(row.get("source_reliability", 0.55) or 0.55)
    return sign * magnitude * confidence * novelty * reliability


def load_events_jsonl(path: str | Path) -> pd.DataFrame:
    rows = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "query" in df.columns:
        df["query"] = df["query"].astype(str).str.upper()
    df["signed_impact"] = df.apply(signed_impact, axis=1)
    return df


def negative_pressure(value: float) -> float:
    return clamp01(-value)


def mean_or_zero(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    return clamp(float(values.mean()))


def event_risk_from_features(row: pd.Series) -> float:
    macro = negative_pressure(row.get("macro_event_pressure", 0.0))
    sector = negative_pressure(row.get("sector_event_pressure", 0.0))
    index = negative_pressure(row.get("index_event_pressure", 0.0))
    peer = negative_pressure(row.get("peer_event_pressure", 0.0))
    ticker = negative_pressure(row.get("ticker_event_pressure", 0.0))
    political = negative_pressure(row.get("political_event_pressure", 0.0))
    valuation = negative_pressure(row.get("valuation_event_pressure", 0.0))
    rates = negative_pressure(row.get("rates_event_pressure", 0.0))
    inflation = negative_pressure(row.get("inflation_event_pressure", 0.0))
    legal = negative_pressure(row.get("legal_event_pressure", 0.0))
    novelty = float(row.get("mean_event_novelty", 0.5) or 0.5)
    agreement = float(row.get("bearish_event_share", 0.0) or 0.0)

    score = (
        0.18 * ticker
        + 0.12 * peer
        + 0.12 * sector
        + 0.10 * index
        + 0.16 * macro
        + 0.08 * rates
        + 0.06 * inflation
        + 0.06 * valuation
        + 0.06 * political
        + 0.04 * legal
        + 0.02 * agreement * novelty
    )
    return round(clamp01(score), 6)


def build_event_features(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()

    rows: list[dict] = []
    for query, group in events.groupby("query"):
        row: dict[str, float | int | str] = {"query": query}
        row["event_count"] = int(len(group))
        row["event_cluster_count"] = int(group["cluster_id"].nunique()) if "cluster_id" in group.columns else 0
        row["mean_event_signed_impact"] = round(mean_or_zero(group["signed_impact"]), 6)
        row["max_abs_event_impact"] = round(float(group["signed_impact"].abs().max()), 6)
        row["mean_event_novelty"] = round(float(group.get("novelty", pd.Series([0.5])).mean()), 6)
        row["mean_source_reliability"] = round(float(group.get("source_reliability", pd.Series([0.55])).mean()), 6)
        row["bearish_event_share"] = round(float(group["direction"].astype(str).str.lower().eq("bearish").mean()), 6)
        row["bullish_event_share"] = round(float(group["direction"].astype(str).str.lower().eq("bullish").mean()), 6)

        for scope, feature in SCOPE_FEATURES.items():
            subset = group[group["scope"].astype(str).str.lower().eq(scope)]
            row[feature] = round(mean_or_zero(subset["signed_impact"]), 6)
            row[f"{feature}_count"] = int(len(subset))

        for event_type, feature in EVENT_TYPE_FEATURES.items():
            subset = group[group["event_type"].astype(str).str.lower().eq(event_type)]
            row[feature] = round(mean_or_zero(subset["signed_impact"]), 6)
            row[f"{feature}_count"] = int(len(subset))

        row["contextual_event_risk"] = event_risk_from_features(pd.Series(row))
        rows.append(row)

    return pd.DataFrame(rows).sort_values("contextual_event_risk", ascending=False)


def merge_event_features(
    *,
    intelligence_features_csv: str | Path,
    event_features_csv: str | Path,
    out_csv: str | Path,
) -> pd.DataFrame:
    base = pd.read_csv(intelligence_features_csv)
    event_features = pd.read_csv(event_features_csv)
    if base.empty:
        out = event_features
    else:
        base["query"] = base["query"].astype(str).str.upper()
        event_features["query"] = event_features["query"].astype(str).str.upper()
        out = base.merge(event_features, on="query", how="left")

        market_rows = event_features[event_features["query"].eq("MARKET")]
        if not market_rows.empty:
            market = market_rows.iloc[-1]
            broadcast_cols = [
                col
                for col in event_features.columns
                if col.startswith(("macro_", "rates_", "inflation_", "index_", "political_", "commodity_"))
                or col in {"contextual_event_risk", "mean_event_signed_impact", "bearish_event_share"}
            ]
            for col in broadcast_cols:
                if col not in out.columns:
                    continue
                market_col = f"market_{col}"
                out[market_col] = market.get(col)
                out[col] = out[col].fillna(market.get(col))

        if "contextual_event_risk" in out.columns and "regime_break_score" in out.columns:
            out["regime_break_score_with_events"] = out[["regime_break_score", "contextual_event_risk"]].max(axis=1)
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    return out
