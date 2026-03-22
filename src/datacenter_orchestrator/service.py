from fastapi import FastAPI
from fastapi.responses import JSONResponse

from datacenter_orchestrator.runtime import build_runner

app = FastAPI(title="lattice", version="0.1.0")


@app.get("/")
def root():
    return {
        "service": "lattice",
        "package": "datacenter_orchestrator",
        "status": "running",
    }


@app.get("/health/live")
def health_live():
    return JSONResponse(content={"status": "alive"})


@app.get("/health/ready")
def health_ready():
    return JSONResponse(content={"status": "ready"})


@app.get("/version")
def version():
    return {
        "service": "lattice",
        "package": "datacenter_orchestrator",
        "version": "0.1.0",
    }


@app.post("/run")
def run_once():
    runner = build_runner()
    runner.run_cycle()
    return {
        "status": "ok",
        "message": "one orchestration cycle completed",
    }
