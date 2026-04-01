from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional
import re


ValueTransform = Callable[[float | int | str], float | int]
LabelExtractor = Callable[[dict | None, str | None], dict[str, str]]


PATH_KEY_RE = re.compile(r"\[([A-Za-z0-9_.-]+)=([^\]]+)\]")


def identity_transform(value: float | int | str) -> float | int:
    if isinstance(value, (int, float)):
        return value
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Unable to convert value {value!r} using identity_transform") from exc


def bool_up_down_transform(value: float | int | str) -> int:
    if isinstance(value, (int, float)):
        return 1 if value else 0

    normalized = str(value).strip().lower()
    if normalized in {"up", "true", "enabled", "active", "established"}:
        return 1
    if normalized in {"down", "false", "disabled", "inactive", "idle"}:
        return 0

    raise ValueError(f"Unsupported boolean style value: {value!r}")


def parse_path_keys(raw_path: str | None) -> dict[str, str]:
    if not raw_path:
        return {}

    parsed: dict[str, str] = {}
    for key, value in PATH_KEY_RE.findall(raw_path):
        parsed[key] = value.strip('"')
    return parsed


def no_label_extraction(payload: dict | None, raw_path: str | None) -> dict[str, str]:
    return {}


def interface_from_payload_or_path(payload: dict | None, raw_path: str | None) -> dict[str, str]:
    if payload:
        for key in ("interface", "name", "if_name", "ifname"):
            value = payload.get(key)
            if value:
                return {"interface": str(value)}

    path_keys = parse_path_keys(raw_path)
    if "name" in path_keys:
        return {"interface": path_keys["name"]}

    return {}


def network_instance_from_payload_or_path(payload: dict | None, raw_path: str | None) -> dict[str, str]:
    labels: dict[str, str] = {}

    if payload:
        for key in ("network_instance", "vrf", "routing_instance"):
            value = payload.get(key)
            if value:
                labels["network_instance"] = str(value)
                break

    path_keys = parse_path_keys(raw_path)
    if "name" in path_keys and "network_instance" not in labels:
        if "/network-instances/network-instance[" in (raw_path or ""):
            labels["network_instance"] = path_keys["name"]

    return labels


def bgp_neighbor_from_payload_or_path(payload: dict | None, raw_path: str | None) -> dict[str, str]:
    labels: dict[str, str] = {}

    if payload:
        for key in ("neighbor", "peer", "peer_address"):
            value = payload.get(key)
            if value:
                labels["peer"] = str(value)
                break

    path_keys = parse_path_keys(raw_path)
    if "neighbor-address" in path_keys and "peer" not in labels:
        labels["peer"] = path_keys["neighbor-address"]
    elif "peer" in path_keys and "peer" not in labels:
        labels["peer"] = path_keys["peer"]

    return labels


@dataclass(frozen=True)
class MetricMappingRule:
    vendor: str
    raw_metric_name: Optional[str] = None
    raw_path: Optional[str] = None
    canonical_metric_name: str = ""
    value_transform: ValueTransform = identity_transform
    label_extractor: LabelExtractor = no_label_extraction
    static_labels: dict[str, str] = field(default_factory=dict)


class MetricMappingRegistry:
    def __init__(self, rules: list[MetricMappingRule]) -> None:
        self.rules = rules

    def resolve(
        self,
        vendor: str,
        raw_metric_name: str | None,
        raw_path: str | None,
    ) -> MetricMappingRule | None:
        for rule in self.rules:
            if rule.vendor != vendor:
                continue

            metric_match = rule.raw_metric_name is None or rule.raw_metric_name == raw_metric_name
            path_match = rule.raw_path is None or rule.raw_path == raw_path

            if metric_match and path_match:
                return rule

        return None


def default_metric_mapping_registry() -> MetricMappingRegistry:
    return MetricMappingRegistry(
        rules=[
            MetricMappingRule(
                vendor="juniper",
                raw_metric_name="bgp.session_state",
                canonical_metric_name="lattice_bgp_session_up",
                value_transform=bool_up_down_transform,
                label_extractor=lambda payload, raw_path: {
                    **network_instance_from_payload_or_path(payload, raw_path),
                    **bgp_neighbor_from_payload_or_path(payload, raw_path),
                },
            ),
            MetricMappingRule(
                vendor="arista",
                raw_metric_name="interfaces.in_octets",
                canonical_metric_name="lattice_interface_in_octets_total",
                value_transform=identity_transform,
                label_extractor=interface_from_payload_or_path,
            ),
            MetricMappingRule(
                vendor="arista",
                raw_metric_name="interfaces.out_octets",
                canonical_metric_name="lattice_interface_out_octets_total",
                value_transform=identity_transform,
                label_extractor=interface_from_payload_or_path,
            ),
            MetricMappingRule(
                vendor="arista",
                raw_metric_name="interfaces.oper_status",
                canonical_metric_name="lattice_interface_oper_up",
                value_transform=bool_up_down_transform,
                label_extractor=interface_from_payload_or_path,
            ),
            MetricMappingRule(
                vendor="juniper",
                raw_metric_name="interfaces.in_octets",
                canonical_metric_name="lattice_interface_in_octets_total",
                value_transform=identity_transform,
                label_extractor=interface_from_payload_or_path,
            ),
            MetricMappingRule(
                vendor="juniper",
                raw_metric_name="interfaces.oper_status",
                canonical_metric_name="lattice_interface_oper_up",
                value_transform=bool_up_down_transform,
                label_extractor=interface_from_payload_or_path,
            ),
            MetricMappingRule(
                vendor="nokia",
                raw_metric_name="interfaces.in_octets",
                canonical_metric_name="lattice_interface_in_octets_total",
                value_transform=identity_transform,
                label_extractor=interface_from_payload_or_path,
            ),
            MetricMappingRule(
                vendor="nokia",
                raw_metric_name="interfaces.oper_status",
                canonical_metric_name="lattice_interface_oper_up",
                value_transform=bool_up_down_transform,
                label_extractor=interface_from_payload_or_path,
            ),
            MetricMappingRule(
                vendor="shared",
                raw_path="/interfaces/interface/state/counters/in-octets",
                canonical_metric_name="lattice_interface_in_octets_total",
                value_transform=identity_transform,
                label_extractor=interface_from_payload_or_path,
            ),
            MetricMappingRule(
                vendor="shared",
                raw_path="/interfaces/interface/state/oper-status",
                canonical_metric_name="lattice_interface_oper_up",
                value_transform=bool_up_down_transform,
                label_extractor=interface_from_payload_or_path,
            ),
            MetricMappingRule(
                vendor="shared",
                raw_path="/network-instances/network-instance/protocols/protocol/bgp/neighbors/neighbor/state/session-state",
                canonical_metric_name="lattice_bgp_session_up",
                value_transform=bool_up_down_transform,
                label_extractor=lambda payload, raw_path: {
                    **network_instance_from_payload_or_path(payload, raw_path),
                    **bgp_neighbor_from_payload_or_path(payload, raw_path),
                },
            ),
        ]
    )
