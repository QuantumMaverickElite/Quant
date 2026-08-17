"""Compatibility entry point for the historical ML-policy validation workflow."""

from backtester.intelligence.ml_policy_validation import *  # noqa: F401,F403
from backtester.intelligence.ml_policy_validation import main


if __name__ == "__main__":
    main()
