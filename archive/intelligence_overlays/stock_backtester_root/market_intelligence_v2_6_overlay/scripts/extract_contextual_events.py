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

from backtester.intelligence.contextual_event_extractor import (
    extract_contextual_events,
    extract_contextual_events_fast,
    make_sentiment_backend,
)
from backtester.intelligence.news_context_ledger import apply_contextual_novelty, context_windows
from backtester.intelligence.semantic_event_clusterer import cluster_events, cluster_summary
from backtester.intelligence.source_loader import load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract contextual market events from intelligence source JSONL.")
    parser.add_argument("--queries", nargs="+", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--events-out", type=Path, default=Path("outputs/intelligence/contextual_events.jsonl"))
    parser.add_argument("--clusters-out", type=Path, default=Path("outputs/intelligence/contextual_event_clusters.csv"))
    parser.add_argument("--context-out", type=Path, default=Path("outputs/intelligence/context_windows.json"))
    parser.add_argument("--sentiment-backend", choices=["heuristic", "finbert", "auto"], default="auto")
    parser.add_argument("--cluster-backend", choices=["heuristic", "sentence-transformers", "auto"], default="auto")
    parser.add_argument(
        "--mode",
        choices=["fast", "exhaustive"],
        default="fast",
        help="fast avoids duplicating macro/sector events for every ticker. exhaustive keeps the older N-by-M behavior.",
    )
    return parser.parse_args()


def write_events(events, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")


def write_cluster_summary(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    docs = load_jsonl(args.input)
    backend = make_sentiment_backend(args.sentiment_backend)
    if args.mode == "fast":
        events = extract_contextual_events_fast(args.queries, docs, sentiment_backend=backend)
    else:
        events = []
        for query in args.queries:
            events.extend(extract_contextual_events(query, docs, sentiment_backend=backend))

    events = cluster_events(events, backend=args.cluster_backend)
    events = apply_contextual_novelty(events)
    clusters = cluster_summary(events)
    windows = context_windows(events)

    write_events(events, args.events_out)
    write_cluster_summary(clusters, args.clusters_out)
    args.context_out.parent.mkdir(parents=True, exist_ok=True)
    args.context_out.write_text(json.dumps(windows, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Events: {len(events)}")
    print(f"Clusters: {len(clusters)}")
    print(f"Saved events: {args.events_out}")
    print(f"Saved clusters: {args.clusters_out}")
    print(f"Saved context windows: {args.context_out}")


if __name__ == "__main__":
    main()
