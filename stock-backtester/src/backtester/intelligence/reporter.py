from __future__ import annotations

import csv
import json
from pathlib import Path

from .schemas import IntelligenceReport


def save_report_json(report: IntelligenceReport, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)


def append_features_csv(report: IntelligenceReport, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    row = {
        "as_of": report.as_of,
        "query": report.query,
        **report.model_features,
        "dominant_pressure": report.dominant_pressure,
        "time_horizon": report.time_horizon,
    }
    exists = Path(path).exists()
    with Path(path).open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)
