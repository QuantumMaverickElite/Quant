#!/usr/bin/env python3
from __future__ import annotations

import argparse

from backtester.intelligence.llm_feature_join import (
    join_llm_features,
    write_joined_llm_features,
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--events",
        default="outputs/intelligence/event_impact_dataset.parquet",
        help="Event-level impact dataset.",
    )
    p.add_argument(
        "--classifications",
        default="outputs/intelligence/llm_event_classifications.parquet",
        help="LLM classification table.",
    )
    p.add_argument(
        "--out",
        default="outputs/intelligence/event_impact_dataset_with_llm.parquet",
        help="Output event-level impact dataset with LLM features.",
    )
    args = p.parse_args()

    df = join_llm_features(
        event_impact_path=args.events,
        classifications_path=args.classifications,
    )
    write_joined_llm_features(df, args.out)

    print(f"rows: {len(df)}")
    print(f"columns: {len(df.columns)}")
    print(f"rows with llm classification: {int(df['has_llm_classification'].sum())}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
