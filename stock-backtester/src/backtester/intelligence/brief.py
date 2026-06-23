from __future__ import annotations

from pathlib import Path

import pandas as pd


ACTION_ORDER = [
    "thesis_break_risk_reduce_or_wait",
    "likely_regime_damage_do_not_average_down",
    "caution_hold_no_adding",
    "same_regime_scale_in_allowed",
    "intelligence_missing_not_evaluated",
    "not_evaluated_historical_row",
]


def read_signals(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported signal file: {path}")


def latest_evaluated_slice(df: pd.DataFrame) -> pd.DataFrame:
    if "intelligence_action_label" not in df.columns:
        raise ValueError("Signal table does not contain intelligence_action_label.")
    evaluated = df[df["intelligence_action_label"].ne("not_evaluated_historical_row")].copy()
    if evaluated.empty:
        return evaluated
    if "date" in evaluated.columns:
        dates = pd.to_datetime(evaluated["date"], errors="coerce")
        latest = dates.max()
        if not pd.isna(latest):
            evaluated = evaluated[dates.eq(latest)].copy()
    return evaluated


def summarize_by_ticker(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    required = {"ticker", "intelligence_action_label"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    agg = {
        "rows": ("ticker", "size"),
    }
    optional_aggs = {
        "regime_break_score": ("regime_break_score", "max"),
        "price_action_risk": ("price_action_risk", "max"),
        "sentiment_score": ("sentiment_score", "mean"),
        "adjusted_confidence": ("adjusted_confidence", "mean"),
        "adjusted_confidence_intelligence_adjusted": ("adjusted_confidence_intelligence_adjusted", "mean"),
        "intelligence_confidence_multiplier": ("intelligence_confidence_multiplier", "mean"),
    }
    for name, spec in optional_aggs.items():
        if spec[0] in df.columns:
            agg[name] = spec

    out = df.groupby("ticker", as_index=False).agg(**agg)
    if "regime_break_score" in out.columns:
        out = out.sort_values("regime_break_score", ascending=False)
    return out


def top_action_tickers(df: pd.DataFrame, action: str, limit: int) -> pd.DataFrame:
    subset = df[df["intelligence_action_label"].eq(action)]
    grouped = summarize_by_ticker(subset)
    return grouped.head(limit)


def format_table(df: pd.DataFrame, cols: list[str], limit: int) -> str:
    if df.empty:
        return "  none"
    cols = [col for col in cols if col in df.columns]
    return df[cols].head(limit).to_string(index=False)


def build_market_intelligence_brief(
    signals: pd.DataFrame,
    *,
    top_n: int = 15,
) -> tuple[str, pd.DataFrame]:
    latest = latest_evaluated_slice(signals)
    if latest.empty:
        return "No evaluated intelligence rows found.", latest

    grouped = summarize_by_ticker(latest)
    action_counts = latest["intelligence_action_label"].value_counts(dropna=False)
    ticker_counts = grouped["ticker"].nunique() if "ticker" in grouped.columns else 0

    caution = top_action_tickers(latest, "caution_hold_no_adding", top_n)
    damage = top_action_tickers(latest, "likely_regime_damage_do_not_average_down", top_n)
    thesis_break = top_action_tickers(latest, "thesis_break_risk_reduce_or_wait", top_n)
    clean = top_action_tickers(latest, "same_regime_scale_in_allowed", top_n)
    missing_latest = top_action_tickers(latest, "intelligence_missing_not_evaluated", top_n)

    lines: list[str] = []
    lines.append("Market Intelligence Brief")
    lines.append("")
    lines.append(f"Evaluated rows: {len(latest):,}")
    lines.append(f"Evaluated tickers: {ticker_counts:,}")
    if "date" in latest.columns:
        lines.append(f"Signal date: {latest['date'].iloc[0]}")
    lines.append("")
    lines.append("Action Counts")
    for action in ACTION_ORDER:
        if action in action_counts:
            lines.append(f"  {action}: {int(action_counts[action]):,}")

    table_cols = [
        "ticker",
        "rows",
        "regime_break_score",
        "price_action_risk",
        "sentiment_score",
        "adjusted_confidence",
        "adjusted_confidence_intelligence_adjusted",
    ]

    lines.append("")
    lines.append("Highest Risk: Thesis Break")
    lines.append(format_table(thesis_break, table_cols, top_n))
    lines.append("")
    lines.append("Likely Regime Damage")
    lines.append(format_table(damage, table_cols, top_n))
    lines.append("")
    lines.append("Caution: Hold / No Adding")
    lines.append(format_table(caution, table_cols, top_n))
    lines.append("")
    lines.append("Cleanest Candidates")
    clean_sorted = clean.sort_values(
        [col for col in ["adjusted_confidence_intelligence_adjusted", "adjusted_confidence"] if col in clean.columns],
        ascending=False,
    ) if not clean.empty else clean
    lines.append(format_table(clean_sorted, table_cols, top_n))
    lines.append("")
    lines.append("Missing Intelligence Coverage")
    lines.append(format_table(missing_latest, table_cols, top_n))

    if "dominant_pressure" in latest.columns:
        pressure_counts = latest["dominant_pressure"].fillna("missing").value_counts().head(10)
        lines.append("")
        lines.append("Dominant Pressure Counts")
        for pressure, count in pressure_counts.items():
            lines.append(f"  {pressure}: {int(count):,}")

    if "intelligence_missing" in latest.columns:
        missing = int(latest["intelligence_missing"].fillna(False).sum())
        lines.append("")
        lines.append(f"Rows with missing intelligence: {missing:,}")

    return "\n".join(lines), grouped


def write_brief(text: str, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text + "\n", encoding="utf-8")
