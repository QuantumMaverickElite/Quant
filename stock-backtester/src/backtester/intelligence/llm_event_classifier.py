from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import re
import time
import urllib.request
import urllib.error
from typing import Any

import pandas as pd


ALLOWED_EVENT_TYPES = {
    "earnings",
    "guidance",
    "analyst_action",
    "deal_partnership",
    "contract_award",
    "product_strategy",
    "regulatory_clinical",
    "legal_investigation",
    "insider_ownership",
    "macro_market",
    "valuation_generic",
    "market_move",
    "other",
}

ALLOWED_DIRECTIONS = {"positive", "negative", "mixed", "neutral", "unclear"}
ALLOWED_SCOPES = {"company", "sector", "market", "macro", "unknown"}
ALLOWED_HORIZONS = {"intraday", "1d", "5d", "20d", "long", "unclear"}
ALLOWED_RISK_FLAGS = {
    "none",
    "legal",
    "regulatory",
    "earnings",
    "guidance",
    "dilution",
    "liquidity",
    "macro",
    "clinical",
    "contract",
    "valuation",
}


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported table type: {path}")


def clean_text(x: object, limit: int = 1800) -> str:
    if x is None or pd.isna(x):
        return ""
    s = re.sub(r"\s+", " ", str(x)).strip()
    return s[:limit]


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def _clamp_float(x: Any, lo: float, hi: float, default: float) -> float:
    try:
        v = float(x)
    except Exception:
        return default
    if pd.isna(v):
        return default
    return max(lo, min(hi, v))


def _enum(x: Any, allowed: set[str], default: str) -> str:
    v = str(x).strip().lower()
    return v if v in allowed else default


def _risk_flags(x: Any) -> list[str]:
    if isinstance(x, str):
        vals = [x]
    elif isinstance(x, list):
        vals = x
    else:
        vals = ["none"]

    out = []
    for v in vals:
        vv = str(v).strip().lower()
        if vv in ALLOWED_RISK_FLAGS and vv not in out:
            out.append(vv)

    return out or ["none"]


def strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def extract_json_object(s: str) -> dict[str, Any]:
    s = strip_code_fence(s)
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        obj = json.loads(s[start : end + 1])
        if isinstance(obj, dict):
            return obj

    raise ValueError("Could not parse JSON object from LLM response")


def validate_classification(raw: dict[str, Any], *, event_id: str) -> dict[str, Any]:
    explanation = clean_text(raw.get("explanation_short", ""), limit=220)

    out = {
        "event_id": event_id,
        "llm_event_type": _enum(raw.get("event_type"), ALLOWED_EVENT_TYPES, "other"),
        "llm_event_subtype": clean_text(raw.get("event_subtype", ""), limit=80),
        "llm_event_direction": _enum(raw.get("event_direction"), ALLOWED_DIRECTIONS, "unclear"),
        "llm_event_scope": _enum(raw.get("event_scope"), ALLOWED_SCOPES, "unknown"),
        "llm_time_horizon": _enum(raw.get("time_horizon"), ALLOWED_HORIZONS, "unclear"),
        "llm_risk_flags": _risk_flags(raw.get("risk_flags")),
        "llm_sentiment_score": _clamp_float(raw.get("sentiment_score"), -1.0, 1.0, 0.0),
        "llm_materiality_score": _clamp_float(raw.get("materiality_score"), 0.0, 1.0, 0.25),
        "llm_novelty_score": _clamp_float(raw.get("novelty_score"), 0.0, 1.0, 0.25),
        "llm_catalyst_strength": _clamp_float(raw.get("catalyst_strength"), 0.0, 1.0, 0.25),
        "llm_confidence": _clamp_float(raw.get("confidence"), 0.0, 1.0, 0.25),
        "llm_explanation_short": explanation,
    }
    return out


def build_prompt(row: pd.Series, *, text_limit: int = 1800) -> str:
    ticker = clean_text(row.get("ticker"), 20)
    company = clean_text(row.get("company_name"), 120)
    provider = clean_text(row.get("provider"), 80)
    source = clean_text(row.get("source"), 120)
    title = clean_text(row.get("title"), 300)
    summary = clean_text(row.get("summary"), text_limit)

    return f"""
You are classifying financial news for a quantitative research pipeline.

Return ONLY valid JSON. Do not include markdown.

Classify what the article says. Do not decide portfolio weights. Do not give investment advice.

Allowed event_type values:
{sorted(ALLOWED_EVENT_TYPES)}

Allowed event_direction values:
{sorted(ALLOWED_DIRECTIONS)}

Allowed event_scope values:
{sorted(ALLOWED_SCOPES)}

Allowed time_horizon values:
{sorted(ALLOWED_HORIZONS)}

Allowed risk_flags values:
{sorted(ALLOWED_RISK_FLAGS)}

Required JSON schema:
{{
  "event_type": "one allowed event_type",
  "event_subtype": "short subtype",
  "event_direction": "positive|negative|mixed|neutral|unclear",
  "event_scope": "company|sector|market|macro|unknown",
  "time_horizon": "intraday|1d|5d|20d|long|unclear",
  "risk_flags": ["one or more allowed flags"],
  "sentiment_score": -1.0,
  "materiality_score": 0.0,
  "novelty_score": 0.0,
  "catalyst_strength": 0.0,
  "confidence": 0.0,
  "explanation_short": "brief reason"
}}

Ticker: {ticker}
Company: {company}
Provider: {provider}
Source: {source}
Title: {title}
Summary: {summary}
""".strip()


def mock_classify(row: pd.Series) -> dict[str, Any]:
    text = f"{row.get('title', '')} {row.get('summary', '')}".lower()
    event_type = "other"
    risk_flags = ["none"]

    checks = [
        ("legal_investigation", ["lawsuit", "investigation", "class action", "shareholder alert", "fraud"], ["legal"]),
        ("regulatory_clinical", ["fda", "clinical", "trial", "phase 1", "phase 2", "phase 3", "approval"], ["regulatory", "clinical"]),
        ("analyst_action", ["upgrade", "downgrade", "price target", "maintains", "initiates", "rating"], ["valuation"]),
        ("earnings", ["earnings", "revenue", "eps", "profit", "margin", "quarter", "q1", "q2", "q3", "q4"], ["earnings"]),
        ("guidance", ["guidance", "outlook", "forecast", "estimates"], ["guidance"]),
        ("deal_partnership", ["partnership", "collaboration", "agreement", "acquisition", "merger"], ["contract"]),
        ("contract_award", ["contract", "awarded", "wins deal"], ["contract"]),
        ("insider_ownership", ["insider", "director", "officer", "rsu", "stock option", "stake"], ["none"]),
        ("valuation_generic", ["enterprise value", "price to book", "price to sales", "valuation", "undervalued"], ["valuation"]),
        ("market_move", ["stock hits", "52-week", "surge", "falls", "jumps", "premarket"], ["none"]),
        ("product_strategy", ["ai", "cloud", "chip", "platform", "launch", "product", "pipeline"], ["none"]),
    ]

    for kind, terms, flags in checks:
        if any(t in text for t in terms):
            event_type = kind
            risk_flags = flags
            break

    pos_terms = ["beat", "upgrade", "raises", "growth", "approval", "wins", "surge", "strong", "upside", "jumps"]
    neg_terms = ["miss", "downgrade", "cuts", "lawsuit", "investigation", "fraud", "falls", "weak", "risk", "uncertainty"]

    pos = sum(1 for t in pos_terms if t in text)
    neg = sum(1 for t in neg_terms if t in text)

    if pos > neg:
        direction = "positive"
    elif neg > pos:
        direction = "negative"
    elif pos == neg == 0:
        direction = "neutral"
    else:
        direction = "mixed"

    sentiment = max(-1.0, min(1.0, (pos - neg) / 3.0))
    materiality = 0.35 + min(0.45, 0.08 * (pos + neg + len([f for f in risk_flags if f != "none"])))

    return validate_classification(
        {
            "event_type": event_type,
            "event_subtype": event_type.replace("_", " "),
            "event_direction": direction,
            "event_scope": "company",
            "time_horizon": "5d",
            "risk_flags": risk_flags,
            "sentiment_score": sentiment,
            "materiality_score": materiality,
            "novelty_score": 0.35,
            "catalyst_strength": materiality,
            "confidence": 0.55,
            "explanation_short": "Mock classifier based on keyword scaffold; replace with API LLM output.",
        },
        event_id=str(row["event_id"]),
    )


def call_openai_compatible(
    *,
    api_base: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout: float = 45.0,
    use_response_format: bool = True,
    max_retries: int = 4,
    retry_base_seconds: float = 2.0,
) -> str:
    url = api_base.rstrip("/") + "/chat/completions"

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You extract structured event fields from financial news. Return only valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }

    if use_response_format:
        payload["response_format"] = {"type": "json_object"}

    last_error = None

    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"LLM API HTTP {e.code}: {body[:500]}")

            # Retry transient provider pressure/rate/server issues.
            if e.code in {408, 409, 429, 500, 502, 503, 504} and attempt < max_retries:
                sleep_for = retry_base_seconds * (2 ** attempt)
                print(f"LLM API transient HTTP {e.code}; retrying in {sleep_for:.1f}s...")
                time.sleep(sleep_for)
                continue

            raise last_error from e

        except urllib.error.URLError as e:
            last_error = RuntimeError(f"LLM API URL error: {e}")
            if attempt < max_retries:
                sleep_for = retry_base_seconds * (2 ** attempt)
                print(f"LLM API URL error; retrying in {sleep_for:.1f}s...")
                time.sleep(sleep_for)
                continue
            raise last_error from e

    raise last_error or RuntimeError("LLM API failed without a captured error")


def load_existing_event_ids(path: str | Path) -> set[str]:
    path = Path(path)
    if not path.exists():
        return set()

    ids: set[str] = set()

    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        obj = json.loads(line)
                        if obj.get("event_id"):
                            ids.add(str(obj["event_id"]))
                    except Exception:
                        continue
        return ids

    try:
        df = read_table(path)
        if "event_id" in df.columns:
            ids.update(df["event_id"].dropna().astype(str))
    except Exception:
        pass

    return ids


def write_classifications(df: pd.DataFrame, out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix.lower() == ".jsonl":
        df.to_json(out_path, orient="records", lines=True, force_ascii=False)
        df.to_parquet(out_path.with_suffix(".parquet"), index=False)
        df.to_csv(out_path.with_suffix(".csv"), index=False)
    elif out_path.suffix.lower() == ".parquet":
        df.to_parquet(out_path, index=False)
        df.to_json(out_path.with_suffix(".jsonl"), orient="records", lines=True, force_ascii=False)
        df.to_csv(out_path.with_suffix(".csv"), index=False)
    elif out_path.suffix.lower() == ".csv":
        df.to_csv(out_path, index=False)
        df.to_parquet(out_path.with_suffix(".parquet"), index=False)
        df.to_json(out_path.with_suffix(".jsonl"), orient="records", lines=True, force_ascii=False)
    else:
        raise ValueError(f"Unsupported output type: {out_path}")


def classify_event_facts(
    *,
    events_path: str | Path,
    out_path: str | Path,
    mode: str = "mock",
    max_rows: int | None = None,
    ticker: str | None = None,
    force: bool = False,
    sleep_seconds: float = 0.0,
    text_limit: int = 1800,
    api_base: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    use_response_format: bool = True,
) -> pd.DataFrame:
    events = read_table(events_path).copy()

    required = {"event_id", "ticker", "event_time", "title", "summary", "provider"}
    missing = sorted(required - set(events.columns))
    if missing:
        raise ValueError(f"event fact table missing required columns: {missing}")

    events["ticker"] = events["ticker"].astype(str).str.upper()
    events["event_id"] = events["event_id"].astype(str)

    if ticker:
        events = events[events["ticker"] == ticker.upper()].copy()

    events = events.sort_values(["event_time", "ticker", "provider"]).reset_index(drop=True)

    existing = set() if force else load_existing_event_ids(out_path)
    if existing:
        events = events[~events["event_id"].isin(existing)].copy()

    if max_rows is not None:
        events = events.head(max_rows).copy()

    rows: list[dict[str, Any]] = []

    if mode == "api":
        api_base = api_base or os.environ.get("OPENAI_COMPAT_API_BASE", "").strip()
        api_key = api_key or os.environ.get("OPENAI_COMPAT_API_KEY", "").strip()
        model = model or os.environ.get("OPENAI_COMPAT_MODEL", "").strip()

        if not api_base or not api_key or not model:
            raise ValueError(
                "API mode requires OPENAI_COMPAT_API_BASE, OPENAI_COMPAT_API_KEY, and OPENAI_COMPAT_MODEL."
            )

    try:
        for _, row in events.iterrows():
            event_id = str(row["event_id"])
            prompt = build_prompt(row, text_limit=text_limit)

            if mode == "mock":
                parsed = mock_classify(row)
                raw_hash = text_hash(prompt)
            elif mode == "api":
                raw = call_openai_compatible(
                    api_base=str(api_base),
                    api_key=str(api_key),
                    model=str(model),
                    prompt=prompt,
                    use_response_format=use_response_format,
                )
                parsed = validate_classification(extract_json_object(raw), event_id=event_id)
                raw_hash = text_hash(raw)
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
            else:
                raise ValueError(f"Unsupported mode: {mode}")

            record = {
                "event_id": event_id,
                "ticker": row.get("ticker"),
                "event_time": str(row.get("event_time")),
                "provider": row.get("provider"),
                "title_hash": text_hash(clean_text(row.get("title"), 300)),
                "classifier_mode": mode,
                "classifier_model": model if mode == "api" else "mock-keyword-scaffold",
                "response_hash": raw_hash,
                **parsed,
            }
            rows.append(record)

    except Exception:
        # Preserve partial progress from quota/rate-limit failures.
        if rows:
            partial = pd.DataFrame(rows)
            partial_path = Path(out_path).with_name(Path(out_path).stem + "_partial.parquet")
            partial.to_parquet(partial_path, index=False)
            partial.to_csv(partial_path.with_suffix(".csv"), index=False)
            print(f"wrote partial progress: {partial_path} rows={len(partial)}")
        raise

    out = pd.DataFrame(rows)

    if len(out) > 0:
        write_classifications(out, out_path)

    return out
