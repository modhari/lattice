from dataclasses import dataclass
from typing import Any


@dataclass
class IntentChange:
    change_id: str
    scope: str
    desired: dict[str, Any]
    current: dict[str, Any]
    diff_summary: str


def build_intent(selected_scenario: str) -> IntentChange:
    """
    Build a test intent based on scenario.
    """

    if selected_scenario == "interface_enable":
        interface_enabled_path = (
            "interfaces/interface[name=Ethernet1]/config/enabled"
        )

        return IntentChange(
            change_id="test-change-iface-enable",
            scope="fabric",
            desired={
                "actions": [
                    {
                        "device": "leaf-01",
                        "model_paths": {
                            interface_enabled_path: True,
                        },
                        "reason": "simulate interface enable",
                    }
                ]
            },
            current={},
            diff_summary="enable interface Ethernet1 on leaf-01",
        )

    elif selected_scenario == "leaf_bgp_disable":
        bgp_leaf_neighbor_enabled_path = (
            "network-instances/network-instance[name=default]/"
            "protocols/protocol[name=BGP]/bgp/neighbors/"
            "neighbor[neighbor-address=10.0.0.1]/config/enabled"
        )

        return IntentChange(
            change_id="test-change-leaf-bgp-disable",
            scope="fabric",
            desired={
                "actions": [
                    {
                        "device": "leaf-01",
                        "model_paths": {
                            bgp_leaf_neighbor_enabled_path: False,
                        },
                        "reason": "simulate BGP neighbor disable on leaf",
                    }
                ]
            },
            current={},
            diff_summary="disable BGP neighbor on leaf-01",
        )

    elif selected_scenario == "spine_bgp_disable":
        bgp_spine_neighbor_enabled_path = (
            "network-instances/network-instance[name=default]/"
            "protocols/protocol[name=BGP]/bgp/neighbors/"
            "neighbor[neighbor-address=10.0.0.101]/config/enabled"
        )

        return IntentChange(
            change_id="test-change-spine-bgp-disable",
            scope="fabric",
            desired={
                "actions": [
                    {
                        "device": "spine-01",
                        "model_paths": {
                            bgp_spine_neighbor_enabled_path: False,
                        },
                        "reason": "simulate BGP neighbor disable on spine",
                    }
                ]
            },
            current={},
            diff_summary="disable BGP neighbor on spine-01",
        )

    else:
        raise ValueError(f"Unknown scenario: {selected_scenario}")
