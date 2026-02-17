"""
Inventory store.

We keep a simple in memory store as the normalized view.
Inventory sources refresh it, and plugins enrich the records.

Why not store raw NetBox objects
We want a stable internal representation that does not leak external schemas
into the engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from datacenter_orchestrator.core.types import DeviceRecord


@dataclass
class InventoryStore:
    """
    Simple device registry keyed by device name.

    This is enough for:
    graph building
    planner context
    policy gate evaluation
    executor targeting
    """

    _devices: Dict[str, DeviceRecord] = None  # type: ignore

    def __post_init__(self) -> None:
        if self._devices is None:
            self._devices = {}

    def add(self, dev: DeviceRecord) -> None:
        """Add or replace a device record."""
        self._devices[dev.name] = dev

    def get(self, name: str) -> Optional[DeviceRecord]:
        """Return device record if present."""
        return self._devices.get(name)

    def all(self) -> List[DeviceRecord]:
        """Return all devices as a list."""
        return list(self._devices.values())

    def names(self) -> List[str]:
        """Return sorted device names. Useful for deterministic outputs."""
        return sorted(self._devices.keys())

    def __iter__(self) -> Iterable[DeviceRecord]:
        """Allow for loops over InventoryStore."""
        return iter(self._devices.values())
