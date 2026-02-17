"""
Orchestration engine.

This engine coordinates:
planning, risk evaluation, optional guarded execution, verification, rollback,
and alert emission.

Determinism and safety
The planner remains deterministic.
Risk assessment is deterministic by default.
A tool hook can enrich evaluation but should not bypass guardrails.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from datacenter_orchestrator.agent.execution_mode import ExecutionMode
from datacenter_orchestrator.agent.guard import ExecutionGuard, GuardDecision
from datacenter_orchestrator.core.types import ChangePlan, IntentChange
from datacenter_orchestrator.execution.base import PlanExecutor
from datacenter_orchestrator.inventory.store import InventoryStore
from datacenter_orchestrator.planner.planner import DeterministicPlanner
from datacenter_orchestrator.planner.risk import PlanRiskAssessment, assess_plan_risk
from datacenter_orchestrator.planner.rollback import build_rollback_plan
from datacenter_orchestrator.planner.verification import evaluate_verification


@dataclass(frozen=True)
class EngineAlert:
    """
    Alert produced by a failed orchestration run.

    severity
    A coarse severity.

    summary
    One line summary.

    risk
    Risk assessment attached for operators.

    verification_failures
    Human readable failures.

    rollback_attempted
    True when rollback logic ran.
    """

    severity: str
    summary: str
    risk: PlanRiskAssessment | None
    verification_failures: list[str]
    rollback_attempted: bool


@dataclass(frozen=True)
class EngineRunResult:
    ok: bool
    plan: ChangePlan | None
    risk: PlanRiskAssessment | None
    guard: GuardDecision | None
    alert: EngineAlert | None


class OrchestrationEngine:
    """
    Orchestration engine.

    planner
    Deterministic planner that converts intent to a ChangePlan.

    executor
    Applies plan to devices.

    guard
    Decides whether the engine is allowed to apply.

    evaluation_tool
    Optional tool hook for MCP integration.
    If present, it can be used to produce risk assessment.
    """

    def __init__(
        self,
        planner: DeterministicPlanner,
        executor: PlanExecutor,
        guard: ExecutionGuard | None = None,
        evaluation_tool: Any | None = None,
    ) -> None:
        self._planner = planner
        self._executor = executor
        self._guard = guard or ExecutionGuard()
        self._evaluation_tool = evaluation_tool

    def _evaluate_risk(self, plan: ChangePlan, inventory: InventoryStore) -> PlanRiskAssessment:
        """
        Evaluate plan risk.

        If a tool is provided, use it.
        Otherwise use deterministic local heuristics.
        """
        if self._evaluation_tool is not None:
            tool = self._evaluation_tool
            return tool.evaluate_plan(plan, inventory)

        return assess_plan_risk(plan, inventory)

    def run_once(self, intent: IntentChange, inventory: InventoryStore) -> EngineRunResult:
        """
        Execute a single intent change.

        Steps
        1) plan
        2) risk assess
        3) guard decision
        4) apply or simulate or dry run
        5) verify
        6) rollback on failure
        """

        plan = self._planner.plan_change(intent, inventory)
        risk = self._evaluate_risk(plan, inventory)
        guard = self._guard.decide(risk)

        if guard.mode == ExecutionMode.dry_run:
            alert = EngineAlert(
                severity="info",
                summary="dry run only, plan not applied",
                risk=risk,
                verification_failures=[],
                rollback_attempted=False,
            )
            return EngineRunResult(ok=False, plan=plan, risk=risk, guard=guard, alert=alert)

        if guard.mode == ExecutionMode.simulate:
            observed = self._simulate_observed_state(plan)
            outcome = evaluate_verification(plan.verification, observed)
            if outcome.ok:
                return EngineRunResult(ok=True, plan=plan, risk=risk, guard=guard, alert=None)

            alert = EngineAlert(
                severity="warning",
                summary="simulation verification failed, plan not applied",
                risk=risk,
                verification_failures=outcome.failures,
                rollback_attempted=False,
            )
            return EngineRunResult(ok=False, plan=plan, risk=risk, guard=guard, alert=alert)

        observed_state, pre_snapshot = self._executor.apply_plan(plan)
        outcome = evaluate_verification(plan.verification, observed_state)

        if outcome.ok:
            return EngineRunResult(ok=True, plan=plan, risk=risk, guard=guard, alert=None)

        rollback_attempted = False
        if plan.rollback.enabled:
            rollback_attempted = True
            rb = build_rollback_plan(plan, pre_snapshot)
            self._executor.apply_plan(rb.plan)

        alert = EngineAlert(
            severity="critical",
            summary="verification failed after apply",
            risk=risk,
            verification_failures=outcome.failures,
            rollback_attempted=rollback_attempted,
        )
        return EngineRunResult(ok=False, plan=plan, risk=risk, guard=guard, alert=alert)

    def _simulate_observed_state(self, plan: ChangePlan) -> dict[str, dict[str, Any]]:
        """
        Build a simulated observed state.

        Simulation rule
        Treat desired model paths as already applied.

        This is intentionally simple. Later you can plug in a fabric simulator
        that models adjacency changes or routing convergence.
        """
        observed: dict[str, dict[str, Any]] = {}
        for act in plan.actions:
            observed[act.device] = dict(act.model_paths)
        return observed
