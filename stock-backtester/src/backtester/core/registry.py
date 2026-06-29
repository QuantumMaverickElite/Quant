"""Simple name-to-object registry used by the reorganization scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class Registry:
    """A tiny explicit registry.

    This avoids hidden import side effects while the repo is being reorganized.
    """

    _items: dict[str, Any] = field(default_factory=dict)

    def register(self, name: str, item: Any, *, replace: bool = False) -> None:
        if not replace and name in self._items:
            raise KeyError(f"Registry item already exists: {name}")
        self._items[name] = item

    def get(self, name: str) -> Any:
        try:
            return self._items[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._items)) or "<empty>"
            raise KeyError(f"Unknown registry item {name!r}. Available: {available}") from exc

    def names(self) -> list[str]:
        return sorted(self._items)

    def items(self) -> Iterable[tuple[str, Any]]:
        return self._items.items()
