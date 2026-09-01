from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester.intelligence.allocator_diagnostics import allocator_summary, write_text_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose allocator changes from market intelligence.")
    parser.add_argument("--signals", required=True, type=Path)
    parser.add_argument("--top-n", type=int, default=25)
    parser.add_argument("--return-col", help="Optional forward-return column for pre/post comparison.")
    parser.add_argument("--out", type=Path, default=Path("outputs/intelligence/allocator_intelligence_diagnostics.txt"))
    return parser.parse_args()


def print_section(title: str, value) -> None:
    if value is None or len(value) == 0:
        return
    print("")
    print(title)
    print(value.to_string(index=False) if hasattr(value, "to_string") else str(value))


def main() -> None:
    args = parse_args()
    diagnostics = allocator_summary(
        signals_path=args.signals,
        top_n=args.top_n,
        return_col=args.return_col,
    )
    write_text_report(diagnostics, args.out)

    print("Allocator Intelligence Diagnostics")
    print(f"Pre column: {diagnostics['pre_col']}")
    print(f"Post column: {diagnostics['post_col']}")

    action_counts = diagnostics.get("action_counts")
    if action_counts is not None and len(action_counts):
        print("")
        print("Action Counts")
        print(action_counts.to_string())

    print_section("Top Post-Intelligence", diagnostics.get("top_post"))
    print_section("Largest Event Boosts", diagnostics.get("boosted"))
    print_section("Largest Event Penalties", diagnostics.get("penalized"))
    print_section("Return Comparison", diagnostics.get("return_compare"))
    print("")
    print(f"Saved diagnostics: {args.out}")


if __name__ == "__main__":
    main()
