from __future__ import annotations

from pathlib import Path
import re
import pandas as pd


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported table type: {path}")


EVENT_TYPES = {
    "earnings": [
        "earnings", "q1", "q2", "q3", "q4", "quarter", "results", "eps",
        "revenue", "profit", "margin", "guidance", "beat", "miss"
    ],
    "analyst_action": [
        "upgrade", "downgrade", "price target", "maintains", "initiates",
        "outperform", "underperform", "buy rating", "sell rating", "neutral rating"
    ],
    "deal_partnership": [
        "deal", "partnership", "collaboration", "merger", "acquisition",
        "acquire", "contract", "awarded", "agreement"
    ],
    "regulatory_clinical": [
        "fda", "clinical", "trial", "phase 1", "phase 2", "phase 3",
        "approval", "regulatory", "pipeline"
    ],
    "legal_investigation": [
        "lawsuit", "investigation", "class action", "securities fraud",
        "shareholder alert", "doj", "antitrust"
    ],
    "insider_ownership": [
        "insider", "director", "officer", "shares sold", "shares bought",
        "stock option", "rsu", "institutional holdings", "stake"
    ],
    "product_strategy": [
        "launch", "platform", "ai", "cloud", "chip", "data center",
        "robotics", "defense", "military", "software", "product"
    ],
    "market_move": [
        "stock gains", "stock falls", "moved higher", "dropped", "surge",
        "tumble", "52-week high", "premarket", "record run"
    ],
    "valuation_generic": [
        "enterprise value", "price to sales", "price to book", "price to earnings",
        "actuals & estimates", "fair value", "undervalued", "valuation"
    ],
}


POSITIVE_TERMS = [
    "beat", "beats", "raises", "raised", "upgrade", "outperform", "buy rating",
    "gains", "surge", "record", "approval", "wins", "growth", "strong",
    "bullish", "higher", "upside", "partnership"
]

NEGATIVE_TERMS = [
    "miss", "misses", "cut", "cuts", "downgrade", "underperform", "sell rating",
    "falls", "dropped", "tumble", "lawsuit", "investigation", "fraud",
    "weak", "bearish", "lower", "risk", "headwind"
]


def safe_text(x: object) -> str:
    if x is None or pd.isna(x):
        return ""
    return str(x)


def normalize_text(x: object) -> str:
    x = safe_text(x).lower()
    x = re.sub(r"[^a-z0-9 $%().,:;&+-]+", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x


def term_count(text: str, terms: list[str]) -> int:
    return sum(1 for term in terms if term in text)


def build_event_impact_dataset(
    *,
    labeled_events_path: str | Path,
    min_label_horizon: int = 5,
) -> pd.DataFrame:
    df = read_table(labeled_events_path).copy()

    required = {"event_id", "ticker", "event_time", "title", "text"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"labeled event table missing required columns: {missing}")

    df["event_time"] = pd.to_datetime(df["event_time"], errors="coerce", utc=True)
    df["text_norm"] = df["text"].map(normalize_text)
    df["title_norm"] = df["title"].map(normalize_text)

    df["title_len"] = df["title"].map(lambda x: len(safe_text(x)))
    df["text_len"] = df["text"].map(lambda x: len(safe_text(x)))
    df["provider"] = df["provider"].astype(str)

    for event_type, terms in EVENT_TYPES.items():
        df[f"event_type_{event_type}"] = df["text_norm"].map(lambda t, terms=terms: int(any(term in t for term in terms)))
        df[f"event_type_{event_type}_count"] = df["text_norm"].map(lambda t, terms=terms: term_count(t, terms))

    df["positive_term_count"] = df["text_norm"].map(lambda t: term_count(t, POSITIVE_TERMS))
    df["negative_term_count"] = df["text_norm"].map(lambda t: term_count(t, NEGATIVE_TERMS))
    df["lexical_sentiment_raw"] = df["positive_term_count"] - df["negative_term_count"]

    df["event_hour_utc"] = df["event_time"].dt.hour
    df["event_dayofweek"] = df["event_time"].dt.dayofweek
    df["is_weekend_event"] = df["event_dayofweek"].isin([5, 6]).astype(int)

    if "event_after_market_close" in df.columns:
        df["event_after_market_close"] = df["event_after_market_close"].astype(bool).astype(int)

    # Provider dummies are model features, not final weights.
    provider_dummies = pd.get_dummies(df["provider"], prefix="provider", dtype=int)
    df = pd.concat([df, provider_dummies], axis=1)

    label_col = f"forward_alpha_vs_spy_{min_label_horizon}d"
    ret_col = f"forward_return_{min_label_horizon}d"

    if label_col not in df.columns:
        raise ValueError(f"missing label column: {label_col}")

    df["target_horizon_days"] = min_label_horizon
    df["target_forward_alpha"] = pd.to_numeric(df[label_col], errors="coerce")
    df["target_forward_return"] = pd.to_numeric(df.get(ret_col), errors="coerce")

    # Regression target plus simple classification target.
    df["target_positive_alpha"] = (df["target_forward_alpha"] > 0).astype("Int64")
    df.loc[df["target_forward_alpha"].isna(), "target_positive_alpha"] = pd.NA

    # Training rows must have labels. Rows without labels can still be scored later, but not trained.
    df["is_trainable"] = df["target_forward_alpha"].notna()

    return df.sort_values(["event_time", "ticker", "provider"]).reset_index(drop=True)


def write_event_impact_dataset(df: pd.DataFrame, out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix.lower() == ".parquet":
        df.to_parquet(out_path, index=False)
        df.to_csv(out_path.with_suffix(".csv"), index=False)
    elif out_path.suffix.lower() == ".csv":
        df.to_csv(out_path, index=False)
        df.to_parquet(out_path.with_suffix(".parquet"), index=False)
    else:
        raise ValueError(f"Unsupported output type: {out_path}")
