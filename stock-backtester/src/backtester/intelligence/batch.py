from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .intelligence_engine import MarketIntelligenceEngine
from .reporter import append_features_csv, save_report_json
from .schemas import IntelligenceReport, SourceDocument


@dataclass(slots=True)
class PriceRiskFeatures:
    peer_divergence: float = 0.0
    volume_shock: float = 0.0
    trend_damage: float = 0.0


def safe_query_name(query: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in query.upper())
    return cleaned.strip("_") or "QUERY"


def batch_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_query_file(path: str | Path) -> list[str]:
    queries: list[str] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            queries.append(line)
    return queries


def load_price_risk_features(path: str | Path | None) -> dict[str, PriceRiskFeatures]:
    if path is None:
        return {}

    features: dict[str, PriceRiskFeatures] = {}
    with Path(path).open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            query = (row.get("query") or row.get("ticker") or row.get("symbol") or "").strip().upper()
            if not query:
                continue
            features[query] = PriceRiskFeatures(
                peer_divergence=float(row.get("peer_divergence") or 0.0),
                volume_shock=float(row.get("volume_shock") or 0.0),
                trend_damage=float(row.get("trend_damage") or 0.0),
            )
    return features


def append_batch_summary_csv(
    *,
    run_id: str,
    reports: list[IntelligenceReport],
    path: str | Path,
) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    exists = Path(path).exists()
    fieldnames = [
        "run_id",
        "as_of",
        "query",
        "sentiment_score",
        "regime_break_score",
        "confidence",
        "dominant_pressure",
        "time_horizon",
        "summary",
    ]

    with Path(path).open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        for report in reports:
            writer.writerow(
                {
                    "run_id": run_id,
                    "as_of": report.as_of,
                    "query": report.query,
                    "sentiment_score": report.sentiment_score,
                    "regime_break_score": report.regime_break_score,
                    "confidence": report.confidence,
                    "dominant_pressure": report.dominant_pressure,
                    "time_horizon": report.time_horizon,
                    "summary": report.summary,
                }
            )


def analyze_batch(
    *,
    queries: list[str],
    documents: list[SourceDocument],
    output_dir: str | Path,
    features_csv: str | Path,
    summary_csv: str | Path,
    price_features: dict[str, PriceRiskFeatures] | None = None,
    default_price_features: PriceRiskFeatures | None = None,
) -> tuple[str, list[IntelligenceReport]]:
    run_id = batch_run_id()
    engine = MarketIntelligenceEngine()
    reports: list[IntelligenceReport] = []
    price_features = price_features or {}
    default_price_features = default_price_features or PriceRiskFeatures()

    for query in queries:
        query_key = query.upper()
        risk = price_features.get(query_key, default_price_features)
        report = engine.analyze(
            query,
            documents,
            peer_divergence=risk.peer_divergence,
            volume_shock=risk.volume_shock,
            trend_damage=risk.trend_damage,
        )
        report_path = Path(output_dir) / run_id / f"{safe_query_name(query)}_report.json"
        save_report_json(report, report_path)
        append_features_csv(report, features_csv)
        reports.append(report)

    append_batch_summary_csv(run_id=run_id, reports=reports, path=summary_csv)
    return run_id, reports
