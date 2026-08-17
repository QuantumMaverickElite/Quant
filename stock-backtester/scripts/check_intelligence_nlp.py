from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.llm.nlp_runtime import check_nlp_runtime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check optional NLP dependencies for market intelligence.")
    parser.add_argument("--load-models", action="store_true", help="Actually load FinBERT and embedding models.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    status = check_nlp_runtime(load_models=args.load_models)
    data = status.to_dict()
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
        return

    print("Market Intelligence NLP Runtime")
    for key, value in data.items():
        print(f"{key}: {value}")

    if not status.transformers_installed or not status.sentence_transformers_installed:
        print("")
        print("Optional NLP packages are missing.")
        print("Install when ready with: pip install -r requirements-intelligence-nlp.txt")


if __name__ == "__main__":
    main()
