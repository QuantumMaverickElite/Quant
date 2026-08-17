from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.llm.contextual_event_extractor import (
    extract_contextual_events,
    extract_contextual_events_fast,
    make_sentiment_backend,
)
from backtester.intelligence.events.news_context_ledger import apply_contextual_novelty, context_windows
from backtester.intelligence.llm.semantic_event_classifier import make_event_classifier
from backtester.intelligence.llm.semantic_event_clusterer import cluster_events, cluster_summary
from backtester.intelligence.source_loader import load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract contextual market events from intelligence source JSONL.")
    parser.add_argument("--queries", nargs="+")
    parser.add_argument("--queries-file", type=Path, help="Optional newline-delimited ticker/query file.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--events-out", type=Path, default=Path("outputs/intelligence/contextual_events.jsonl"))
    parser.add_argument("--clusters-out", type=Path, default=Path("outputs/intelligence/contextual_event_clusters.csv"))
    parser.add_argument("--context-out", type=Path, default=Path("outputs/intelligence/context_windows.json"))
    parser.add_argument("--sentiment-backend", choices=["heuristic", "finbert", "auto"], default="auto")
    parser.add_argument("--event-classifier", choices=["heuristic", "semantic", "auto"], default="heuristic")
    parser.add_argument("--cluster-backend", choices=["heuristic", "sentence-transformers", "auto"], default="auto")
    parser.add_argument("--nlp-device", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--embedding-device", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--event-classifier-device", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--event-classifier-min-confidence", type=float, default=0.20)
    parser.add_argument(
        "--mode",
        choices=["fast", "exhaustive"],
        default="fast",
        help="fast avoids duplicating macro/sector events for every ticker. exhaustive keeps the older N-by-M behavior.",
    )
    return parser.parse_args()


def resolve_queries(args: argparse.Namespace) -> list[str]:
    queries: list[str] = []
    if args.queries:
        queries.extend(args.queries)
    if args.queries_file:
        queries.extend(
            line.strip()
            for line in args.queries_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = query.strip().upper()
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    if not deduped:
        raise SystemExit("Provide --queries or --queries-file.")
    return deduped


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
    queries = resolve_queries(args)
    if args.nlp_device:
        os.environ["INTELLIGENCE_NLP_DEVICE"] = args.nlp_device
    if args.embedding_device:
        os.environ["INTELLIGENCE_EMBEDDING_DEVICE"] = args.embedding_device
    if args.event_classifier_device:
        os.environ["INTELLIGENCE_EVENT_CLASSIFIER_DEVICE"] = args.event_classifier_device
    docs = load_jsonl(args.input)
    backend = make_sentiment_backend(args.sentiment_backend)
    event_classifier = make_event_classifier(
        args.event_classifier,
        device=args.event_classifier_device,
        min_confidence=args.event_classifier_min_confidence,
    )
    if args.mode == "fast":
        events = extract_contextual_events_fast(
            queries,
            docs,
            sentiment_backend=backend,
            event_classifier=event_classifier,
        )
    else:
        events = []
        for query in queries:
            events.extend(
                extract_contextual_events(
                    query,
                    docs,
                    sentiment_backend=backend,
                    event_classifier=event_classifier,
                )
            )

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
