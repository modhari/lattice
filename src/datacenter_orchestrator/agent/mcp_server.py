"""
Minimal MCP-style HTTP server.

This exposes a single tool:
evaluate_plan

It is intentionally simple:
- JSON over HTTP
- no external dependencies
- deterministic fallback logic

This is not a production hardened server.
It is a clean integration layer for orchestration research.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from datacenter_orchestrator.inventory.store import InventoryStore
from datacenter_orchestrator.planner.risk import assess_plan_risk
from datacenter_orchestrator.core.types import ChangePlan


class MCPRequestHandler(BaseHTTPRequestHandler):
    """
    Very small MCP-like protocol.

    POST /evaluate_plan
    {
        "plan": {...},
        "inventory": {...}
    }
    """

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/evaluate_plan":
            self._send_json(404, {"error": "unknown endpoint"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)
        data = json.loads(raw.decode("utf-8"))

        try:
            plan_dict = data["plan"]
            inventory_dict = data["inventory"]

            plan = ChangePlan.from_dict(plan_dict)
            inventory = InventoryStore.from_dict(inventory_dict)

            risk = assess_plan_risk(plan, inventory)

            self._send_json(
                200,
                {
                    "risk_level": risk.risk_level,
                    "blast_radius_score": risk.blast_radius_score,
                    "requires_approval": risk.requires_approval,
                    "reasons": risk.reasons,
                    "evidence": risk.evidence,
                },
            )
        except Exception as exc:  # safe boundary
            self._send_json(500, {"error": str(exc)})


def run_mcp_server(host: str = "127.0.0.1", port: int = 8085) -> None:
    server = HTTPServer((host, port), MCPRequestHandler)
    print(f"MCP server running on http://{host}:{port}")
    server.serve_forever()
