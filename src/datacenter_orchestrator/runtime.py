from __future__ import annotations

import os
from dataclasses import dataclass

# Core runner that drives the orchestration loop
from datacenter_orchestrator.agent.runner import AgentRunner, RunnerConfig

# Strongly typed models for inventory and intent
from datacenter_orchestrator.core.types import (
    CapabilityClass,
    Confidence,
    DeviceEndpoints,
    DeviceIdentity,
    DeviceRecord,
    DeviceRole,
    FabricLocation,
    IntentChange,
    Link,
    LinkKind,
)

# Mock executor (dry-run). Replace later with real gNMI / device executor
from datacenter_orchestrator.execution.mock import InMemoryExecutor

# Interface for intent sources
from datacenter_orchestrator.intent.base import IntentSource

# In-memory inventory store
from datacenter_orchestrator.inventory.store import InventoryStore


# ---------------------------------------------------------------------
# Inventory Plugin
# ---------------------------------------------------------------------
# This defines the network topology that the system reasons about.
# In real systems this would come from NetBox, IPAM, or a topology service.
# ---------------------------------------------------------------------
class StaticInventoryPlugin:
    def load(self) -> InventoryStore:
        store = InventoryStore()

        # -------------------------
        # Leaf 01
        # -------------------------
        leaf_01 = DeviceRecord(
            name="leaf-01",
            role=DeviceRole.leaf,  # important for risk classification
            identity=DeviceIdentity(
                vendor="Arista",
                model="DCS-7280",
                os_name="EOS",
                os_version="4.31.1F",
                serial="LEAF01",
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
            # Fabric connectivity → used later for blast radius calculations
            links=[
                Link("Ethernet49", "spine-01", "Ethernet1", LinkKind.fabric),
                Link("Ethernet50", "spine-02", "Ethernet1", LinkKind.fabric),
            ],
            bandwidth_class=CapabilityClass(
                name="100g",
                confidence=Confidence.high,
                evidence=[],
            ),
        )

        # -------------------------
        # Leaf 02
        # -------------------------
        leaf_02 = DeviceRecord(
            name="leaf-02",
            role=DeviceRole.leaf,
            identity=DeviceIdentity(
                vendor="Arista",
                model="DCS-7280",
                os_name="EOS",
                os_version="4.31.1F",
                serial="LEAF02",
            ),
            endpoints=DeviceEndpoints(
                mgmt_host="leaf-02.lab.local",
                gnmi_host="leaf-02.lab.local",
                gnmi_port=57400,
            ),
            location=FabricLocation(
                pod="pod-1",
                rack="rack-2",
                plane="default",
            ),
            links=[
                Link("Ethernet49", "spine-01", "Ethernet2", LinkKind.fabric),
                Link("Ethernet50", "spine-02", "Ethernet2", LinkKind.fabric),
            ],
            bandwidth_class=CapabilityClass(
                name="100g",
                confidence=Confidence.high,
                evidence=[],
            ),
        )

        # -------------------------
        # Spine 01
        # -------------------------
        spine_01 = DeviceRecord(
            name="spine-01",
            role=DeviceRole.spine,  # higher impact device → higher risk weight
            identity=DeviceIdentity(
                vendor="Arista",
                model="DCS-7800",
                os_name="EOS",
                os_version="4.31.1F",
                serial="SPINE01",
            ),
            endpoints=DeviceEndpoints(
                mgmt_host="spine-01.lab.local",
                gnmi_host="spine-01.lab.local",
                gnmi_port=57400,
            ),
            location=FabricLocation(
                pod="pod-1",
                rack="spine-rack-1",
                plane="default",
            ),
            links=[],  # spines are aggregation points
        )

        # -------------------------
        # Spine 02
        # -------------------------
        spine_02 = DeviceRecord(
            name="spine-02",
            role=DeviceRole.spine,
            identity=DeviceIdentity(
                vendor="Arista",
                model="DCS-7800",
                os_name="EOS",
                os_version="4.31.1F",
                serial="SPINE02",
            ),
            endpoints=DeviceEndpoints(
                mgmt_host="spine-02.lab.local",
                gnmi_host="spine-02.lab.local",
                gnmi_port=57400,
            ),
            location=FabricLocation(
                pod="pod-1",
                rack="spine-rack-2",
                plane="default",
            ),
            links=[],
        )

        # Add all devices to inventory
        store.add(leaf_01)
        store.add(leaf_02)
        store.add(spine_01)
        store.add(spine_02)

        return store


# ---------------------------------------------------------------------
# Intent Source
# ---------------------------------------------------------------------
# This feeds intents into the system.
# Right now it's in-memory (test scenarios), later this becomes:
# - API driven
# - Agent driven
# - Telemetry triggered
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class InMemoryIntentSource(IntentSource):
    intents: list[IntentChange]

    def fetch(self) -> list[IntentChange]:
        return list(self.intents)


# ---------------------------------------------------------------------
# Runner Builder
# ---------------------------------------------------------------------
# This is the entry point used by the API layer.
# It wires:
# - scenario → intent
# - inventory → topology
# - executor → execution layer
# ---------------------------------------------------------------------
def build_runner(scenario: str | None = None) -> AgentRunner:
    # Priority:
    # 1. scenario from API (nre_agent)
    # 2. fallback to env variable
    selected_scenario = scenario or os.environ.get("NRE_SCENARIO", "leaf_bgp_disable")

    # -------------------------------------------------
    # Scenario: Interface Enable (LOW / MEDIUM RISK)
    # -------------------------------------------------
    if selected_scenario == "interface_enable":
        test_intent = IntentChange(
            change_id="test-change-iface-enable",
            scope="fabric",
            desired={
                "actions": [
                    {
                        "device": "leaf-01",
                        "model_paths": {
                            "interfaces/interface[name=Ethernet1]/config/enabled": True
                        },
                        "reason": "enable interface for controlled test",
                    }
                ]
            },
            current={},
            diff_summary="enable interface on leaf-01",
        )

    # -------------------------------------------------
    # Scenario: Leaf BGP Disable (HIGH RISK)
    # -------------------------------------------------
    elif selected_scenario == "leaf_bgp_disable":
        test_intent = IntentChange(
            change_id="test-change-leaf-bgp-disable",
            scope="fabric",
            desired={
                "actions": [
                    {
                        "device": "leaf-01",
                        "model_paths": {
                            "network-instances/network-instance[name=default]/protocols/protocol[name=BGP]/bgp/neighbors/neighbor[neighbor-address=10.0.0.1]/config/enabled": False
                        },
                        "reason": "simulate BGP neighbor disable on leaf",
                    }
                ]
            },
            current={},
            diff_summary="disable BGP neighbor on leaf-01",
        )

    # -------------------------------------------------
    # Scenario: Spine BGP Disable (VERY HIGH RISK)
    # -------------------------------------------------
    elif selected_scenario == "spine_bgp_disable":
        test_intent = IntentChange(
            change_id="test-change-spine-bgp-disable",
            scope="fabric",
            desired={
                "actions": [
                    {
                        "device": "spine-01",
                        "model_paths": {
                            "network-instances/network-instance[name=default]/protocols/protocol[name=BGP]/bgp/neighbors/neighbor[neighbor-address=10.0.0.101]/config/enabled": False
                        },
                        "reason": "simulate BGP neighbor disable on spine",
                    }
                ]
            },
            current={},
            diff_summary="disable BGP neighbor on spine-01",
        )

    else:
        raise ValueError(f"unsupported NRE_SCENARIO: {selected_scenario}")

    # Wrap intent into source
    intent_source = InMemoryIntentSource(intents=[test_intent])

    # Build the runner
    return AgentRunner(
        executor=InMemoryExecutor(),          # dry-run execution
        inventory_plugin=StaticInventoryPlugin(),  # topology
        intent_source=intent_source,          # intent feed
        config=RunnerConfig(),                # runtime config
    )
