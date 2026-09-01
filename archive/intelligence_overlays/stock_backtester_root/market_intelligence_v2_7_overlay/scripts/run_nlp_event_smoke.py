from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.contextual_event_extractor import extract_contextual_events_fast, make_sentiment_backend
from backtester.intelligence.semantic_event_classifier import make_event_classifier
from backtester.intelligence.semantic_event_clusterer import cluster_events, cluster_summary
from backtester.intelligence.source_loader import load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small NLP event extraction smoke test.")
    parser.add_argument("--queries", nargs="+", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--limit-docs", type=int, default=30)
    parser.add_argument("--sentiment-backend", choices=["heuristic", "finbert", "auto"], default="finbert")
    parser.add_argument("--event-classifier", choices=["heuristic", "semantic", "auto"], default="semantic")
    parser.add_argument("--cluster-backend", choices=["heuristic", "sentence-transformers", "auto"], default="sentence-transformers")
    parser.add_argument("--nlp-device", choices=["auto", "cpu", "cuda"], default=None)
    parser.add_argument("--embedding-device", choices=["auto", "cpu", "cuda"], default=None)
    parser.add_argument("--event-classifier-device", choices=["auto", "cpu", "cuda"], default=None)
    parser.add_argument("--event-classifier-min-confidence", type=float, default=0.20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.nlp_device:
        os.environ["INTELLIGENCE_NLP_DEVICE"] = args.nlp_device
    if args.embedding_device:
        os.environ["INTELLIGENCE_EMBEDDING_DEVICE"] = args.embedding_device
    if args.event_classifier_device:
        os.environ["INTELLIGENCE_EVENT_CLASSIFIER_DEVICE"] = args.event_classifier_device
    docs = load_jsonl(args.input)[: args.limit_docs]
    sentiment = make_sentiment_backend(args.sentiment_backend)
    event_classifier = make_event_classifier(
        args.event_classifier,
        device=args.event_classifier_device,
        min_confidence=args.event_classifier_min_confidence,
    )
    events = extract_contextual_events_fast(
        args.queries,
        docs,
        sentiment_backend=sentiment,
        event_classifier=event_classifier,
    )
    events = cluster_events(events, backend=args.cluster_backend)
    clusters = cluster_summary(events)

    print(f"Documents: {len(docs)}")
    print(f"Events: {len(events)}")
    print(f"Clusters: {len(clusters)}")
    print("")
    for event in events[:20]:
        print(
            f"{event.query} {event.direction} conf={event.confidence:.3f} "
            f"type={event.event_type} type_conf={event.event_type_confidence:.3f} "
            f"scope={event.scope} scope_conf={event.scope_confidence:.3f} "
            f"sentiment={event.sentiment_model} classifier={event.event_classifier}: {event.text[:180]}"
        )


if __name__ == "__main__":
    main()
