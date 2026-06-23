from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence import MarketIntelligenceEngine
from backtester.intelligence.reporter import append_features_csv, save_report_json
from backtester.intelligence.source_loader import from_texts


docs = from_texts(
    [
        {
            "source": "Reuters",
            "title": "Software stocks fall as investors question AI valuations",
            "text": """
            PLTR declined with other software and AI stocks as investors cited valuation concerns
            and multiple compression. The broader Nasdaq also fell as Treasury yields rose.
            Analysts said the move appeared tied to sector pressure rather than a new company-specific
            guidance cut.
            """,
        },
        {
            "source": "Manual note",
            "title": "Palantir contract momentum",
            "text": """
            PLTR continues to benefit from strong AI demand and government contract interest.
            No new negative guidance was reported today.
            """,
        },
    ]
)

report = MarketIntelligenceEngine().analyze(
    "PLTR",
    docs,
    peer_divergence=0.15,
    volume_shock=0.20,
    trend_damage=0.10,
)

print(report.summary)
print(report.model_features)

save_report_json(report, "outputs/intelligence/PLTR_report.json")
append_features_csv(report, "outputs/intelligence/intelligence_features.csv")
