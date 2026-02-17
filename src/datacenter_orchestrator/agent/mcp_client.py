"""
MCP client for plan evaluation.

This client calls the local MCP server over HTTP.
If the server is unreachable, it raises.
Engine can catch and fallback to deterministic mode.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from datacenter_orchestrator.core.types import ChangePlan
from datacenter_orchestrator.inventory.store import InventoryStore
from datacenter_orchestrator.planner.risk import PlanRiskAssessment, RiskLevel
from datacenter_orchestrator.core.serialization import (
    change_plan_to_dict,
    inventory_to_dict,
)

@dataclass(frozen=True)
class MCPClient:
    base_url: str = "http://127.0.0.1:8085"

    def evaluate_plan(
        self,
        plan: ChangePlan,
        inventory: InventoryStore,
    ) -> PlanRiskAssessment:
        payload = {
            "plan": change_plan_to_dict(plan),
            "inventory": inventory_to_dict(inventory),
        }

        req = Request(
            url=f"{self.base_url}/evaluate_plan",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        return PlanRiskAssessment(
            risk_level=RiskLevel(data["risk_level"]),
            blast_radius_score=int(data["blast_radius_score"]),
            requires_approval=bool(data["requires_approval"]),
            reasons=list(data["reasons"]),
            evidence=dict(data["evidence"]),
        )
