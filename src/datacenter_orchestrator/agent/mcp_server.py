from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from datacenter_orchestrator.mcp.codec import (
    decode_request,
    encode_response_error,
    encode_response_ok,
)
from datacenter_orchestrator.mcp.errors import McpValidationError
from datacenter_orchestrator.mcp.schemas import McpApiVersion, McpMethod


class McpHandler(BaseHTTPRequestHandler):
    def _read_json(self) -> Any:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/mcp":
            self._send_json(
                404,
                encode_response_error(McpApiVersion.v1, "unknown", "not_found", "unknown endpoint"),
            )
            return

        try:
            payload = self._read_json()
            req = decode_request(payload)

            if req.method != McpMethod.evaluate_plan:
                self._send_json(
                    400,
                    encode_response_error(
                        req.api_version,
                        req.request_id,
                        "unsupported_method",
                        "method not supported",
                    ),
                )
                return

            plan = req.params.get("plan")
            inventory = req.params.get("inventory")

            if not isinstance(plan, dict):
                raise McpValidationError("params.plan must be an object")
            if not isinstance(inventory, dict):
                raise McpValidationError("params.inventory must be an object")

            risk = self._evaluate_plan_dicts(plan, inventory)

            self._send_json(
                200,
                encode_response_ok(
                    req.api_version,
                    req.request_id,
                    {
                        "risk_level": risk["risk_level"],
                        "blast_radius_score": risk["blast_radius_score"],
                        "requires_approval": risk["requires_approval"],
                        "reasons": risk["reasons"],
                        "evidence": risk["evidence"],
                    },
                ),
            )

        except McpValidationError as exc:
            self._send_json(
                400,
                encode_response_error(McpApiVersion.v1, "unknown", "validation_error", str(exc)),
            )
        except Exception as exc:
            self._send_json(
                500,
                encode_response_error(McpApiVersion.v1, "unknown", "server_error", str(exc)),
            )

    def _evaluate_plan_dicts(
        self, 
        plan: dict[str, Any], 
        inventory: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Deterministic evaluation from JSON inputs.

        For 10.2, we keep this minimal and safe.
        We convert only what we need to call assess_plan_risk.

        If your assess_plan_risk requires ChangePlan and InventoryStore objects,
        we will add a strict adapter in the next small patch.

        For now, we return a placeholder conservative result to keep server safe.
        """
        _ = plan
        _ = inventory
        return {
            "risk_level": "high",
            "blast_radius_score": 100,
            "requires_approval": True,
            "reasons": ["server adapter not yet bound to internal risk logic"],
            "evidence": {},
        }


def run_mcp_server(host: str = "127.0.0.1", port: int = 8085) -> None:
    server = HTTPServer((host, port), McpHandler)
    print(f"mcp server listening on http://{host}:{port}/mcp")
    server.serve_forever()
