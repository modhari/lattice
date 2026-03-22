"""
Runtime wiring for lattice.

This module builds a runnable AgentRunner with:
- static inventory
- in memory intent source
- in memory executor

Used by the service layer to trigger orchestration cycles.
"""

from dataclasses import dataclass

from datacenter_orchestrator.agent.runner import AgentRunner, RunnerConfig
from datacenter_orchestrator.core.types import (
    CapabilityClass,
    Confidence,
    DeviceEndpoints,
    DeviceIdentity,
    DeviceRecord,
    DeviceRole,
    FabricLocation,
    IntentChange,
)
from datacenter_orchestrator.execution.mock import InMemoryExecutor
from datacenter_orchestrator.intent.base import IntentSource
from datacenter_orchestrator.inventory.store import InventoryStore


class StaticInventoryPlugin:
    """
    Minimal inventory plugin for testing.

    Returns a one device inventory so the planner can validate actions.
    """

    def load(self) -> InventoryStore:
        store = InventoryStore()

        leaf = DeviceRecord(
            name="leaf-01",
            role=DeviceRole.leaf,
            identity=DeviceIdentity(
                vendor="Arista",
                model="DCS-7280",
                os_name="EOS",
                os_version="4.31.1F",
                serial="TEST1234",
            ),
            endpoints=DeviceEndpoints(
                mgmt_host="leaf-01.lab.local",
                gnmi_host="leaf-01.lab.local",
                gnmi_port=57400,
            ),
            location=FabricLocation(
                pod="pod-1",
                rack="rack-1",
                plane="default",
            ),
            links=[],
            bandwidth_class=CapabilityClass(
                name="100g",
                confidence=Confidence.high,
                evidence=[],
            ),
        )

        store.add(leaf)
        return store


@dataclass(frozen=True)
class InMemoryIntentSource(IntentSource):
    """
    Minimal in memory intent source for testing.
    """

    intents: list[IntentChange]

    def fetch(self) -> list[IntentChange]:
        return list(self.intents)


def build_runner() -> AgentRunner:
    """
    Construct a runnable AgentRunner instance with test data.
    """

    test_intent = IntentChange(
        change_id="test-change-1",
        scope="fabric",
        desired={
            "actions": [
                {
                    "device": "leaf-01",
                    "model_paths": {
                        "interfaces/interface[name=Ethernet1]/config/enabled": True
                    },
                    "reason": "test action from runtime",
                }
            ]
        },
        current={},
        diff_summary="test diff",
    )

    intent_source = InMemoryIntentSource(intents=[test_intent])

    return AgentRunner(
        executor=InMemoryExecutor(),
        inventory_plugin=StaticInventoryPlugin(),
        intent_source=intent_source,
        config=RunnerConfig(),
    )
