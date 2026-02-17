"""
Deterministic planner.

Purpose
This planner converts an IntentChange into a structured ChangePlan that the
orchestration engine can execute safely.

Why deterministic
Agentic systems can propose ideas, but the final plan that touches devices must
be stable, auditable, and repeatable. This planner is designed to be strict and
predictable.

Input shape expectations
IntentChange.desired should contain either:
1  A list of actions under the key "actions"
   Each action is a dict with:
   - device: str
   - model_paths: dict[str, Any]
   - reason: str optional

2  Or a single device block under the key "device" and "model_paths"

If the structure is missing or wrong, we raise ValueError so the caller can
report a clear error to the user.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from datacenter_orchestrator.core.types import (
    ChangeAction,
    ChangePlan,
    IntentChange,
    RollbackSpec,
    VerificationSpec,
)
from datacenter_orchestrator.inventory.store import InventoryStore


@dataclass
class PlannerConfig:
    """
    Planner configuration.

    max_devices_low_risk
    If a plan touches no more than this many devices, it is low risk by default.

    verification_window_seconds
    How long verification should consider the post change state stable.
    """

    max_devices_low_risk: int = 2
    verification_window_seconds: int = 60


class DeterministicPlanner:
    """
    A strict planner that produces ChangePlan from IntentChange.

    This planner does not call external models.
    Later you can add an AgenticPlanner that produces an intent proposal.
    The output of that model should still be converted into a ChangePlan here
    or via another deterministic step.
    """

    def __init__(self, config: PlannerConfig | None = None) -> None:
        self._config = config or PlannerConfig()

    def plan_change(self, intent: IntentChange, inventory: InventoryStore) -> ChangePlan:
        """
        Convert intent into an executable ChangePlan.

        We use inventory only for basic sanity checks such as verifying device names.
        More complex checks belong in the policy gate layer later.
        """

        actions = self._parse_actions(intent.desired)
        self._validate_actions_exist_in_inventory(actions, inventory)

        risk = self._compute_risk(actions)
        verification = self._build_verification(intent, actions)
        rollback = self._build_rollback_spec(intent, actions)

        explanation = (
            "Plan created from declarative intent. "
            f"Device count {len(actions)}. "
            f"Risk {risk}. "
            f"Verification checks {len(verification.checks)}."
        )

        return ChangePlan(
            plan_id=intent.change_id,
            actions=actions,
            verification=verification,
            rollback=rollback,
            risk=risk,
            explanation=explanation,
        )

    def _parse_actions(self, desired: dict[str, Any]) -> list[ChangeAction]:
        """
        Parse actions from the desired dict.

        Accepted formats are documented in the module docstring.
        """

        if "actions" in desired:
            raw_actions = desired["actions"]
            if not isinstance(raw_actions, list):
                raise ValueError("desired.actions must be a list")

            actions: list[ChangeAction] = []
            for idx, raw in enumerate(raw_actions):
                if not isinstance(raw, dict):
                    raise ValueError(f"desired.actions item {idx} must be a dict")

                device = raw.get("device")
                model_paths = raw.get("model_paths")
                reason = raw.get("reason", "intent action")

                if not isinstance(device, str) or not device:
                    raise ValueError(f"desired.actions item {idx} missing device str")

                if not isinstance(model_paths, dict) or not model_paths:
                    raise ValueError(f"desired.actions item {idx} missing model_paths dict")

                actions.append(ChangeAction(device=device, model_paths=model_paths, reason=str(reason)))

            return actions

        device = desired.get("device")
        model_paths = desired.get("model_paths")
        reason = desired.get("reason", "intent action")

        if isinstance(device, str) and isinstance(model_paths, dict) and model_paths:
            return [ChangeAction(device=device, model_paths=model_paths, reason=str(reason))]

        raise ValueError("desired must include actions list or device and model_paths")

    def _validate_actions_exist_in_inventory(
        self,
        actions: list[ChangeAction],
        inventory: InventoryStore,
    ) -> None:
        """
        Ensure all devices referenced by the plan exist in inventory.

        This prevents accidental attempts to configure unknown devices.
        """

        missing: list[str] = []
        for act in actions:
            if inventory.get(act.device) is None:
                missing.append(act.device)

        if missing:
            missing_sorted = ", ".join(sorted(set(missing)))
            raise ValueError(f"plan references devices not present in inventory: {missing_sorted}")

    def _compute_risk(self, actions: list[ChangeAction]) -> str:
        """
        Compute a coarse risk level.

        This is intentionally simple.
        The policy gate layer will enforce finer rules later.
        """

        if len(actions) <= self._config.max_devices_low_risk:
            return "low"
        if len(actions) <= 10:
            return "medium"
        return "high"

    def _build_verification(self, intent: IntentChange, actions: list[ChangeAction]) -> VerificationSpec:
        """
        Build a verification spec.

        For now we build path equality checks for every model path we write.
        This is a safe default because it verifies that the device accepted the intended state.

        Later you will add protocol level checks such as BGP session state and route counts.
        """

        checks: list[dict[str, Any]] = []
        for act in actions:
            for path, expected in act.model_paths.items():
                checks.append(
                    {
                        "type": "path_equals",
                        "device": act.device,
                        "path": str(path),
                        "expected": expected,
                    }
                )

        probes: list[dict[str, Any]] = []
        return VerificationSpec(
            checks=checks,
            probes=probes,
            window_seconds=self._config.verification_window_seconds,
        )

    def _build_rollback_spec(self, intent: IntentChange, actions: list[ChangeAction]) -> RollbackSpec:
        """
        Build a rollback spec.

        Default
        Rollback enabled and triggered by any verification failure.

        You can make this stricter later, for example only rollback for critical checks.
        """

        _ = intent
        _ = actions

        return RollbackSpec(
            enabled=True,
            triggers=["any_verification_failure"],
        )
