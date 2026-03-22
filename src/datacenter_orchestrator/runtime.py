"""
Runtime wiring for lattice.

This module builds a runnable AgentRunner with:
- static inventory
- static intent
- mock executor

Used by the service layer to trigger orchestration cycles.
"""

from datacenter_orchestrator.agent.runner import AgentRunner, RunnerConfig
from datacenter_orchestrator.core.types import IntentChange
from datacenter_orchestrator.execution.mock import MockPlanExecutor
from datacenter_orchestrator.intent.static_source import StaticIntentSource
from datacenter_orchestrator.inventory.store import InventoryStore


class StaticInventoryPlugin:
    """
    Minimal inventory plugin for testing.

    Returns an empty inventory for now.
    """

    def load(self) -> InventoryStore:
        return InventoryStore()


def build_runner() -> AgentRunner:
    """
    Construct a runnable AgentRunner instance with test data.
    """

    # --- Test Intent ---
    test_intent = IntentChange(
        change_id="test-change-1",
        scope="fabric",
        desired={"action": "enable_interface"},
        current={"action": "disabled"},
        diff_summary="test diff",
    )

    intent_source = StaticIntentSource(intents=[test_intent])

    return AgentRunner(
        executor=MockPlanExecutor(),
        inventory_plugin=StaticInventoryPlugin(),
        intent_source=intent_source,
        config=RunnerConfig(),
    )
