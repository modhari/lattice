# Lattice

Agentic AI powered data center orchestration engine for CLOS fabrics.
It ingests intent and inventory, validates topology and external connectivity,
plans changes, applies config via gNMI, verifies state, and rolls back on failure.

## Architecture

![Orchestration Engine](docs/images/orchestration_engine.png)

## What this repo contains

1. Source plugins for inventory and intent ingestion
2. Fabric graph builder and CLOS topology validation
3. Capacity math and a fabric sizing engine
4. Agentic planner interface that outputs a structured change plan
5. Executor interface for model driven gNMI config
6. Verification catalog and rollback plumbing
7. Policy gate that blocks unsafe plans
8. Staging and production aware workflows

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
python -m datacenter_orchestrator.main
