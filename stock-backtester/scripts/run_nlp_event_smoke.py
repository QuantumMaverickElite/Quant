from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.llm.contextual_event_extractor import extract_contextual_events_fast, make_sentiment_backend
from backtester.intelligence.llm.semantic_event_classifier import make_event_classifier
from backtester.intelligence.llm.semantic_event_clusterer import cluster_events, cluster_summary
from backtester.intelligence.source_loader import load_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small NLP event extraction smoke test.")
    parser.add_argument("--queries", nargs="+")
    parser.add_argument("--queries-file", type=Path, help="Optional newline-delimited ticker/query file.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--limit-docs", type=int, default=30)
    parser.add_argument("--sentiment-backend", choices=["heuristic", "finbert", "auto"], default="finbert")
    parser.add_argument("--event-classifier", choices=["heuristic", "semantic", "auto"], default="semantic")
    parser.add_argument("--cluster-backend", choices=["heuristic", "sentence-transformers", "auto"], default="sentence-transformers")
    parser.add_argument("--nlp-device", choices=["auto", "cpu", "cuda"], default=None)
    parser.add_argument("--embedding-device", choices=["auto", "cpu", "cuda"], default=None)
    parser.add_argument("--event-classifier-device", choices=["auto", "cpu", "cuda"], default=None)
    parser.add_argument("--event-classifier-min-confidence", type=float, default=0.20)
    parser.add_argument("--show-context", action="store_true")
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


def main() -> None:
    args = parse_args()
    queries = resolve_queries(args)
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
        queries,
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
        if event.raw_semantic_event_type and event.raw_semantic_event_type != event.event_type:
            print(f"  raw_type: {event.raw_semantic_event_type}")
        if event.raw_semantic_scope and event.raw_semantic_scope != event.scope:
            print(f"  raw_scope: {event.raw_semantic_scope}")
        if args.show_context and event.classification_context:
            print(f"  context: {event.classification_context[:260]}")


if __name__ == "__main__":
    main()
