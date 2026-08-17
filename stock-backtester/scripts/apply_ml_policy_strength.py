"""Compatibility entry point for the historical ML-policy application workflow."""

from backtester.intelligence.ml_policy_application import *  # noqa: F401,F403
from backtester.intelligence.ml_policy_application import main


if __name__ == "__main__":
    main()
