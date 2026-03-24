from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from datacenter_orchestrator.runtime import build_runner

app = FastAPI(title="lattice", version="0.1.0")


@app.get("/")
def root() -> dict[str, str]:
    """
    Basic service identity endpoint.
    """
    return {
        "service": "lattice",
        "package": "datacenter_orchestrator",
        "status": "running",
    }


@app.get("/health/live")
def health_live() -> JSONResponse:
    """
    Liveness probe.
    """
    return JSONResponse(content={"status": "alive"})


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    """
    Readiness probe.
    """
    return JSONResponse(content={"status": "ready"})


@app.get("/version")
def version() -> dict[str, str]:
    """
    Simple version endpoint.
    """
    return {
        "service": "lattice",
        "package": "datacenter_orchestrator",
        "version": "0.1.0",
    }


@app.post("/run")
async def run_once(request: Request) -> dict:
    """
    Execute one orchestration cycle.

    Request body may optionally provide:
    {
      "scenario": "leaf_bgp_disable"
    }

    Response returns:
    - high level status
    - selected scenario
    - intent id
    - risk details if present
    """

    body = (
        await request.json()
        if request.headers.get("content-type", "").startswith("application/json")
        else {}
    )

    scenario = body.get("scenario")

    # Build a runner for the requested scenario
    runner = build_runner(scenario=scenario)

    # Execute one cycle and collect structured results
    results = runner.run_cycle()

    if not results:
        return {
            "status": "ok",
            "message": "one orchestration cycle completed",
            "scenario": scenario,
            "results": [],
        }

    # For now the runtime only feeds one intent per cycle,
    # so return the first result as the primary response.
    result = results[0]

    risk_payload = None
    if result.risk is not None:
        risk_payload = {
            "risk_level": result.risk.risk_level.value,
            "blast_radius_score": result.risk.blast_radius_score,
            "requires_approval": result.risk.requires_approval,
            "reasons": result.risk.reasons,
            "evidence": result.risk.evidence,
        }

    alert_payload = None
    if result.alert is not None:
        alert_payload = {
            "summary": result.alert.summary,
        }

    return {
        "status": "ok",
        "message": "one orchestration cycle completed",
        "scenario": scenario,
        "result": {
            "ok": result.ok,
            "intent_id": getattr(result, "intent_id", None),
            "risk": risk_payload,
            "alert": alert_payload,
        },
    }
