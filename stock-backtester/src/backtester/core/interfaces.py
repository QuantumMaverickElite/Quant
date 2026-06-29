"""Stable interfaces for research engines.

These interfaces are intentionally small. The first reorganization goal is to make
Kalman, RMT, Wasserstein, Cox, HRP, SABR, and future modules look the same from
the experiment runner's point of view.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Protocol, runtime_checkable


@dataclass(frozen=True)
class EngineContext:
    """Runtime context shared by feature, risk, regime, and allocation engines."""

    run_id: str
    as_of: str | None = None
    root: Path = Path(".")
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class EngineResult:
    """Standard result envelope returned by engines.

    `data` is deliberately typed as Any so existing pandas/numpy/polars objects can
    be adopted without forcing a dependency decision in Phase 0.
    """

    name: str
    data: Any
    metadata: MutableMapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class FeatureEngine(Protocol):
    """Transforms market/research inputs into feature tables."""

    name: str

    def fit(self, data: Any, context: EngineContext | None = None) -> "FeatureEngine":
        """Fit optional state. Stateless engines may return self."""

    def transform(self, data: Any, context: EngineContext | None = None) -> EngineResult:
        """Return a feature table or feature tensor."""


@runtime_checkable
class RiskEngine(Protocol):
    """Produces risk features, risk states, or stress metrics."""

    name: str

    def compute(self, data: Any, context: EngineContext | None = None) -> EngineResult:
        """Return risk output in a standard envelope."""


@runtime_checkable
class RegimeEngine(Protocol):
    """Classifies or scores market regimes."""

    name: str

    def score(self, data: Any, context: EngineContext | None = None) -> EngineResult:
        """Return regime labels, scores, or transition probabilities."""


@runtime_checkable
class Allocator(Protocol):
    """Converts signals/risk inputs into portfolio weights."""

    name: str

    def allocate(self, data: Any, context: EngineContext | None = None) -> EngineResult:
        """Return portfolio weights or orders."""


@runtime_checkable
class ScenarioGenerator(Protocol):
    """Generates deterministic or stochastic stress scenarios."""

    name: str

    def sample(self, data: Any, n: int, context: EngineContext | None = None) -> EngineResult:
        """Return sampled scenarios."""
