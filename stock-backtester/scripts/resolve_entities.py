from __future__ import annotations

import argparse

from backtester.intelligence.entity_resolver import EntityResolver, default_entity_master_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test market-intelligence entity resolution.")
    parser.add_argument("--entity-master", default=str(default_entity_master_path()))
    parser.add_argument("--query", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--min-score", type=float, default=0.35)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    resolver = EntityResolver.from_csv(args.entity_master)
    record = resolver.resolve_query(args.query)
    matched, score = resolver.query_relevance(args.query, args.text)
    print(f"query={args.query}")
    print(f"resolved_ticker={record.ticker if record else ''}")
    print(f"resolved_name={(record.common_name or record.legal_name) if record else ''}")
    print(f"score={score:.4f}")
    print(f"matched_terms={matched}")
    print(f"passes_min_score={score >= args.min_score}")
    text_matches = resolver.resolve_text_to_entities(args.text, min_score=args.min_score)
    print("text_entities=" + ",".join(f"{item.ticker}:{item.score:.2f}" for item in text_matches[:20]))


if __name__ == "__main__":
    main()
