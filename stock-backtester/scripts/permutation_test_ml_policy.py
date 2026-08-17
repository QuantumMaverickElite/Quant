"""Compatibility entry point for the historical ML-policy permutation research workflow."""

from backtester.intelligence.ml_policy.permutation import *  # noqa: F401,F403
from backtester.intelligence.ml_policy.permutation import main


if __name__ == "__main__":
    main()
