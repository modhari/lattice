from datacenter_orchestrator.agent.runner import AgentRunner, RunnerConfig
from datacenter_orchestrator.execution.mock import MockPlanExecutor
from datacenter_orchestrator.intent.static_source import StaticIntentSource
from datacenter_orchestrator.inventory.store import InventoryStore


class StaticInventoryPlugin:
    def load(self) -> InventoryStore:
        return InventoryStore()


def build_runner() -> AgentRunner:
    return AgentRunner(
        executor=MockPlanExecutor(),
        inventory_plugin=StaticInventoryPlugin(),
        intent_source=StaticIntentSource(intents=[]),
        config=RunnerConfig(),
    )
