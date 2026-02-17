"""
Orchestration engine loop.

Purpose
Coordinate planning, execution, verification, rollback, and alert generation.

This file defines:
- An executor interface the real gNMI adapter will implement
- A single run_once workflow for one intent change
- A small alert structure that can be wired into notifications later

Design note
This engine is intentionally synchronous and simple.
It is easier to test and reason about.
You can add concurrency later at the executor layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from datacenter_orchestrator.core.types import ChangePlan, IntentChange
from datacenter_orchestrator.inventory.store import InventoryStore
from datacenter_orchestrator.planner import DeterministicPlanner
from datacenter_orchestrator.planner.rollback import RollbackBuildResult, build_rollback_plan
from datacenter_orchestrator.planner.verification import VerificationOutcome, evaluate_verification


class PlanExecutor(Protocol):
    """
    Executor interface.

    apply_plan must:
    1  Capture a snapshot before applying changes
    2  Apply the model path updates
    3  Return observed state after apply

    The snapshot enables deterministic rollback.
    """

    def apply_plan(
        self,
        plan: ChangePlan,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        """
        Return (observed_state, pre_snapshot).

        observed_state
        device name -> model path -> value

        pre_snapshot
        device name -> model path -> value
        """


@dataclass
class DetailedAlert:
    """
    Detailed alert describing a failed change.

    This can be sent to chat, email, or an incident system later.
    """

    plan_id: str
    severity: str
    summary: str
    verification_failures: list[str]
    verification_evidence: dict[str, object]
    rollback_attempted: bool
    rollback_missing_paths: list[str]


@dataclass
class RunResult:
    """
    Result of a run_once call.

    ok
    True means apply and verification succeeded.

    alert
    Populated when ok is False.
    """

    ok: bool
    alert: DetailedAlert | None


class OrchestrationEngine:
    """
    Orchestrates a single intent change through plan, apply, verify, rollback.

    This class does not ingest from Git or NetBox.
    Ingestion is a separate layer that will feed IntentChange objects into run_once.
    """

    def __init__(
        self,
        planner: DeterministicPlanner,
        executor: PlanExecutor,
    ) -> None:
        self._planner = planner
        self._executor = executor

    def run_once(self, intent: IntentChange, inventory: InventoryStore) -> RunResult:
        """
        Execute one intent change.

        Workflow
        1  Build a ChangePlan
        2  Apply plan through executor, collecting pre snapshot and observed state
        3  Verify observed state
        4  If verification fails and rollback enabled, build rollback plan and apply it
        5  Produce a detailed alert if anything fails
        """

        plan = self._planner.plan_change(intent=intent, inventory=inventory)

        observed_state, pre_snapshot = self._executor.apply_plan(plan)

        outcome = evaluate_verification(plan.verification, observed_state)
        if outcome.ok:
            return RunResult(ok=True, alert=None)

        rollback_attempted = False
        rollback_missing_paths: list[str] = []

        if plan.rollback.enabled:
            rollback_attempted = True
            rb: RollbackBuildResult = build_rollback_plan(plan, pre_snapshot)
            rollback_missing_paths = rb.missing_paths
            self._executor.apply_plan(rb.plan)

        alert = self._build_alert(plan, outcome, rollback_attempted, rollback_missing_paths)
        return RunResult(ok=False, alert=alert)

    def _build_alert(
        self,
        plan: ChangePlan,
        outcome: VerificationOutcome,
        rollback_attempted: bool,
        rollback_missing_paths: list[str],
    ) -> DetailedAlert:
        """
        Create a detailed alert object.

        Severity logic is simple for now.
        You can later map risk and failure type into paging policies.
        """

        severity = "critical" if plan.risk in {"high"} else "warning"
        summary = "verification failed after apply"

        return DetailedAlert(
            plan_id=plan.plan_id,
            severity=severity,
            summary=summary,
            verification_failures=outcome.failures,
            verification_evidence=outcome.evidence,
            rollback_attempted=rollback_attempted,
            rollback_missing_paths=rollback_missing_paths,
        )
