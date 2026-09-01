from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.claim_extractor import extract_claims
from backtester.intelligence.evidence_graph import evidence_graph_features, orthogonalize_claims
from backtester.intelligence.source_loader import load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect duplicate-aware evidence clusters for a news JSONL.")
    parser.add_argument("--query", required=True, help="Ticker, index, or market topic, e.g. PLTR, QQQ, MARKET.")
    parser.add_argument("--input", required=True, type=Path, help="JSONL with source/title/text/url/published_at fields.")
    parser.add_argument("--events-json", type=Path, default=Path("outputs/intelligence/evidence_events.json"))
    parser.add_argument("--claims-csv", type=Path, default=Path("outputs/intelligence/evidence_claims.csv"))
    parser.add_argument("--print-json", action="store_true")
    return parser.parse_args()


def write_events(path: Path, events: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump([event.to_dict() for event in events], f, indent=2)


def write_claims(path: Path, claims: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "entity",
        "event_id",
        "direction",
        "category",
        "magnitude",
        "trust_score",
        "novelty",
        "orthogonal_weight",
        "duplicate_count",
        "independent_source_count",
        "contradiction_count",
        "source_diversity",
        "source",
        "source_title",
        "published_at",
        "claim",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for claim in claims:
            writer.writerow({field: getattr(claim, field) for field in fields})


def main() -> None:
    args = parse_args()
    docs = load_jsonl(args.input)
    raw_claims = extract_claims(args.query, docs)
    claims, events = orthogonalize_claims(raw_claims)
    features = evidence_graph_features(events, raw_claim_count=len(raw_claims))

    write_events(args.events_json, events)
    write_claims(args.claims_csv, claims)

    payload = {
        "query": args.query.upper(),
        "features": {key: round(float(value), 4) for key, value in features.items()},
        "events": [event.to_dict() for event in events],
    }
    if args.print_json:
        print(json.dumps(payload, indent=2))
    else:
        print(
            f"{args.query.upper()}: {int(features['raw_claim_count'])} claims collapsed into "
            f"{int(features['orthogonal_event_count'])} orthogonal events."
        )
        print(f"Average trust: {features['avg_event_trust']:.3f}")
        print(f"Saved events: {args.events_json}")
        print(f"Saved claims: {args.claims_csv}")


if __name__ == "__main__":
    main()
