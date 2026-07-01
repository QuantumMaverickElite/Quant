from __future__ import annotations

from pathlib import Path
import ast
import re
import pandas as pd


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".jsonl":
        return pd.read_json(path, lines=True)
    raise ValueError(f"Unsupported table type: {path}")


def safe_col(x: object) -> str:
    s = str(x).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "unknown"


def parse_risk_flags(x: object) -> list[str]:
    if x is None:
        return ["none"]

    if isinstance(x, (list, tuple, set)):
        vals = list(x)
    elif hasattr(x, "tolist") and not isinstance(x, str):
        vals = x.tolist()
    elif isinstance(x, str):
        raw = x.strip()
        if not raw:
            vals = ["none"]
        elif raw.startswith("["):
            try:
                vals = ast.literal_eval(raw)
            except Exception:
                vals = [raw]
        else:
            vals = [raw]
    else:
        try:
            if pd.isna(x):
                return ["none"]
        except Exception:
            pass
        vals = [str(x)]

    out = []
    for v in vals:
        vv = safe_col(v)
        if vv and vv not in out:
            out.append(vv)

    return out or ["none"]


def add_llm_feature_columns(classifications: pd.DataFrame) -> pd.DataFrame:
    cls = classifications.copy()

    required = {"event_id"}
    missing = sorted(required - set(cls.columns))
    if missing:
        raise ValueError(f"classification table missing required columns: {missing}")

    cls["event_id"] = cls["event_id"].astype(str)

    categorical = [
        "llm_event_type",
        "llm_event_direction",
        "llm_event_scope",
        "llm_time_horizon",
    ]

    for col in categorical:
        if col in cls.columns:
            cls[col] = cls[col].map(safe_col)
            dummies = pd.get_dummies(cls[col], prefix=col, dtype=int)
            cls = pd.concat([cls, dummies], axis=1)

    if "llm_risk_flags" in cls.columns:
        risk_lists = cls["llm_risk_flags"].map(parse_risk_flags)
        all_flags = sorted({flag for flags in risk_lists for flag in flags})
        for flag in all_flags:
            cls[f"llm_risk_flag_{flag}"] = risk_lists.map(lambda flags, flag=flag: int(flag in flags))

    numeric_cols = [
        "llm_sentiment_score",
        "llm_materiality_score",
        "llm_novelty_score",
        "llm_catalyst_strength",
        "llm_confidence",
    ]

    for col in numeric_cols:
        if col not in cls.columns:
            cls[col] = pd.NA
        cls[col] = pd.to_numeric(cls[col], errors="coerce")

    keep_cols = ["event_id"]

    passthrough = [
        "classifier_mode",
        "classifier_model",
        "llm_event_type",
        "llm_event_subtype",
        "llm_event_direction",
        "llm_event_scope",
        "llm_time_horizon",
        "llm_risk_flags",
        "llm_explanation_short",
    ]

    for col in passthrough + numeric_cols:
        if col in cls.columns and col not in keep_cols:
            keep_cols.append(col)

    generated = [
        c for c in cls.columns
        if c.startswith("llm_event_type_")
        or c.startswith("llm_event_direction_")
        or c.startswith("llm_event_scope_")
        or c.startswith("llm_time_horizon_")
        or c.startswith("llm_risk_flag_")
    ]

    keep_cols.extend([c for c in generated if c not in keep_cols])

    return cls[keep_cols].drop_duplicates("event_id", keep="last")


def join_llm_features(
    *,
    event_impact_path: str | Path,
    classifications_path: str | Path,
) -> pd.DataFrame:
    events = read_table(event_impact_path).copy()
    cls = add_llm_feature_columns(read_table(classifications_path))

    if "event_id" not in events.columns:
        raise ValueError("event impact table missing event_id")

    events["event_id"] = events["event_id"].astype(str)

    out = events.merge(cls, on="event_id", how="left", validate="many_to_one")
    out["has_llm_classification"] = out["llm_confidence"].notna().astype(int)

    return out


def write_joined_llm_features(df: pd.DataFrame, out_path: str | Path) -> None:
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
