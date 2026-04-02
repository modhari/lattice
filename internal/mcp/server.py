from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from internal.bgp.anomaly_detector import BgpAnomalyDetector
from internal.bgp.history_store import BgpHistoryStore
from internal.bgp.route_state_tracker import BgpRouteStateTracker, build_demo_routes
from internal.mcp.capability_registry import CapabilityRegistry

LOG = logging.getLogger(__name__)

APP = FastAPI(title="Lattice MCP Server", version="0.1.0")


class CapabilityInvokeRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@dataclass
class IdempotencyRecord:
    capability: str
    key: str
    response: dict[str, Any]
    created_at_ms: int


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._records: dict[str, IdempotencyRecord] = {}

    def get(self, capability: str, key: str) -> dict[str, Any] | None:
        record = self._records.get(f"{capability}:{key}")
        return record.response if record else None

    def put(self, capability: str, key: str, response: dict[str, Any]) -> None:
        self._records[f"{capability}:{key}"] = IdempotencyRecord(
            capability=capability,
            key=key,
            response=response,
            created_at_ms=_now_ms(),
        )


class JsonlAuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf_8") as handle:
            handle.write(json.dumps(record) + "\n")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _build_demo_state() -> tuple[BgpRouteStateTracker, BgpHistoryStore]:
    tracker = BgpRouteStateTracker()
    snapshot_1, snapshot_2 = build_demo_routes()

    tracker.ingest_snapshot(snapshot_1[0].timestamp_ms, snapshot_1)
    tracker.ingest_snapshot(snapshot_2[0].timestamp_ms, snapshot_2)

    from_ts = snapshot_1[0].timestamp_ms
    to_ts = snapshot_2[0].timestamp_ms

    summaries = tracker.peer_summaries_at(to_ts)
    events = tracker.route_events_for_diff(from_ts, to_ts)

    anomalies = BgpAnomalyDetector(
        received_major_drop_pct=20.0,
        received_critical_drop_pct=50.0,
        advertised_major_drop_pct=20.0,
        advertised_critical_drop_pct=50.0,
        churn_event_threshold=3,
    ).detect_from_tracker(
        tracker=tracker,
        from_timestamp_ms=from_ts,
        to_timestamp_ms=to_ts,
    )

    history_store = BgpHistoryStore()
    history_store.store_route_snapshot_rows(snapshot_1)
    history_store.store_route_snapshot_rows(snapshot_2)
    history_store.store_peer_summary_rows(summaries)
    history_store.store_route_event_rows(events)
    history_store.store_anomaly_rows(anomalies)

    return tracker, history_store


TRACKER, HISTORY_STORE = _build_demo_state()
REGISTRY = CapabilityRegistry(
    tracker=TRACKER,
    history_store=HISTORY_STORE,
)
IDEMPOTENCY = InMemoryIdempotencyStore()
AUDIT = JsonlAuditLogger(Path("data/generated/mcp/audit_log.jsonl"))

# Replace this with your real secret loading later.
EXPECTED_BEARER_TOKEN = "local-dev-token"


def _require_auth(authorization: str | None) -> None:
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    if not secrets.compare_digest(token, EXPECTED_BEARER_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid token")


@APP.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "capabilities": REGISTRY.list_capabilities(),
    }


@APP.post("/mcp/capability/{capability_name}")
async def invoke_capability(
    capability_name: str,
    body: CapabilityInvokeRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    x_idempotency_key: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_auth(authorization)

    handler = REGISTRY.get_handler(capability_name)
    if handler is None:
        raise HTTPException(status_code=404, detail="Unknown capability")

    idempotency_key = x_idempotency_key
    if idempotency_key:
        cached = IDEMPOTENCY.get(capability_name, idempotency_key)
        if cached is not None:
            AUDIT.write(
                {
                    "timestamp_ms": _now_ms(),
                    "event": "capability_cache_hit",
                    "capability": capability_name,
                    "idempotency_key": idempotency_key,
                    "client": request.client.host if request.client else None,
                }
            )
            return cached

    try:
        response = handler(payload=body.payload)
    except ValueError as exc:
        AUDIT.write(
            {
                "timestamp_ms": _now_ms(),
                "event": "capability_validation_error",
                "capability": capability_name,
                "payload": body.payload,
                "error": str(exc),
                "client": request.client.host if request.client else None,
            }
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        LOG.exception("Capability invocation failed for %s", capability_name)
        AUDIT.write(
            {
                "timestamp_ms": _now_ms(),
                "event": "capability_internal_error",
                "capability": capability_name,
                "payload": body.payload,
                "error": repr(exc),
                "client": request.client.host if request.client else None,
            }
        )
        raise HTTPException(status_code=500, detail="Internal capability error") from exc

    if idempotency_key:
        IDEMPOTENCY.put(capability_name, idempotency_key, response)

    AUDIT.write(
        {
            "timestamp_ms": _now_ms(),
            "event": "capability_invoked",
            "capability": capability_name,
            "idempotency_key": idempotency_key,
            "payload": body.payload,
            "response_summary": {
                "status": response.get("status"),
                "capability": response.get("capability"),
            },
            "client": request.client.host if request.client else None,
        }
    )

    return response
