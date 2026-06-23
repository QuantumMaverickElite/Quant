from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence import MarketIntelligenceEngine
from backtester.intelligence.reporter import append_features_csv, save_report_json
from backtester.intelligence.source_loader import load_jsonl


DEFAULT_OUTPUT_DIR = Path("outputs/intelligence")
DEFAULT_FEATURES_CSV = DEFAULT_OUTPUT_DIR / "intelligence_features.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Market Intelligence on trusted article/news JSONL.")
    parser.add_argument("--query", required=True, help="Ticker, index, or market topic, e.g. PLTR, QQQ, MARKET.")
    parser.add_argument("--input", required=True, type=Path, help="JSONL file with source/title/text fields.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--features-csv", type=Path, default=DEFAULT_FEATURES_CSV)
    parser.add_argument("--peer-divergence", type=float, default=0.0)
    parser.add_argument("--volume-shock", type=float, default=0.0)
    parser.add_argument("--trend-damage", type=float, default=0.0)
    parser.add_argument("--print-json", action="store_true")
    return parser.parse_args()


def safe_query_name(query: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in query.upper())
    return cleaned.strip("_") or "QUERY"


def main() -> None:
    args = parse_args()
    docs = load_jsonl(args.input)
    report = MarketIntelligenceEngine().analyze(
        args.query,
        docs,
        peer_divergence=args.peer_divergence,
        volume_shock=args.volume_shock,
        trend_damage=args.trend_damage,
    )

    report_path = args.output_dir / f"{safe_query_name(args.query)}_report.json"
    save_report_json(report, report_path)
    append_features_csv(report, args.features_csv)

    if args.print_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.summary)
        print(report.model_features)
        print(f"Saved report: {report_path}")
        print(f"Appended features: {args.features_csv}")


if __name__ == "__main__":
    main()
