"""Compatibility entry point for the historical ML-policy sweep workflow."""

from backtester.intelligence.ml_policy.sweep import *  # noqa: F401,F403
from backtester.intelligence.ml_policy.sweep import main


if __name__ == "__main__":
    main()
