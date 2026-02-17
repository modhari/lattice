"""
Serialization helpers.

Purpose
Convert ChangePlan and InventoryStore into JSON safe dictionaries
for MCP transport.

We keep this separate from types to avoid polluting core models.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from datacenter_orchestrator.core.types import ChangePlan
from datacenter_orchestrator.inventory.store import InventoryStore


# --------------------------
# ChangePlan serialization
# --------------------------

def change_plan_to_dict(plan: ChangePlan) -> dict[str, Any]:
    """
    Convert ChangePlan to dict.

    Uses dataclasses.asdict but ensures enums become strings.
    """

    def normalize(obj: Any) -> Any:
        if hasattr(obj, "value"):  # Enum
            return obj.value
        if isinstance(obj, dict):
            return {k: normalize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [normalize(v) for v in obj]
        return obj

    raw = asdict(plan)
    return normalize(raw)


# --------------------------
# Inventory serialization
# --------------------------

def inventory_to_dict(store: InventoryStore) -> dict[str, Any]:
    """
    Convert InventoryStore into dictionary form.
    """
    devices = []
    for dev in store.all():
        devices.append(asdict(dev))

    return {"devices": devices}
