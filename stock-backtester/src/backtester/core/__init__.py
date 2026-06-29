"""Core abstractions for the stock-backtester research platform."""

from backtester.core.interfaces import (
    Allocator,
    EngineContext,
    EngineResult,
    FeatureEngine,
    RegimeEngine,
    RiskEngine,
    ScenarioGenerator,
)
from backtester.core.registry import Registry

__all__ = [
    "Allocator",
    "EngineContext",
    "EngineResult",
    "FeatureEngine",
    "RegimeEngine",
    "RiskEngine",
    "ScenarioGenerator",
    "Registry",
]
