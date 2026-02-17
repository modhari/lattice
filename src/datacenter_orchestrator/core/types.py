"""
Core types.

This file defines the shared data structures used across the engine.

Important design choice
We keep these types vendor neutral and transport neutral.

Vendor neutral means:
We describe desired state using model paths and values, not CLI commands.

Transport neutral means:
ExecClient may implement gNMI, or other model driven APIs, but callers do not care.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DeviceRole(str, Enum):
    """
    Device roles in a CLOS fabric.

    leaf
      Server facing leaf.

    spine
      Spine in a two tier or three tier design.

    super_spine
      Optional third tier for very large fabrics.

    border_leaf
      Leaf used for external connectivity in a border pod model.

    border_spine
      Only used when smaller fabrics connect externally via spines.
      In that model, all spines must connect externally.

    services_leaf
      Leaf dedicated to service appliances.

    edge_leaf
      Optional role for edge aggregation patterns.
    """

    leaf = "leaf"
    spine = "spine"
    super_spine = "super_spine"
    border_leaf = "border_leaf"
    border_spine = "border_spine"
    services_leaf = "services_leaf"
    edge_leaf = "edge_leaf"


class LinkKind(str, Enum):
    """
    Link classification.

    fabric
      Internal CLOS fabric link.

    mlag_peer
      Leaf to leaf peer link used for MLAG pairs.

    external
      External neighbor not managed in inventory.

    internet
      External link intended for internet facing connectivity.

    wan
      External link intended for private WAN connectivity.

    These distinctions allow the validator to enforce:
    border pod isolation model
    or spine external symmetry model
    """

    fabric = "fabric"
    mlag_peer = "mlag_peer"
    external = "external"
    internet = "internet"
    wan = "wan"


class Confidence(str, Enum):
    """
    Confidence for derived facts.

    high means we observed it directly from device or trusted source
    medium means inferred from multiple signals
    low means heuristic or incomplete evidence
    """

    high = "high"
    medium = "medium"
    low = "low"


@dataclass(frozen=True)
class Evidence:
    """
    Evidence explains why we believe a derived fact is true.

    Example:
    source might be netbox, gnmi, napalm, or a capability catalog
    detail captures a short reason string
    """

    source: str
    detail: str


@dataclass
class CapabilityClass:
    """
    A normalized capability classification.

    We store normalized classes instead of raw numbers because the orchestrator
    often makes decisions in buckets such as:
    small, medium, large table scale
    low, medium, high buffers
    """

    name: str
    confidence: Confidence
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class DeviceIdentity:
    """
    Vendor identity for a device.

    This is used by adapter selection, compatibility checks, and reporting.
    """

    vendor: str
    model: str
    os_name: str
    os_version: str
    serial: str = ""


@dataclass
class DeviceEndpoints:
    """
    How to reach a device.

    mgmt_host can be used for auxiliary protocols.
    gnmi_host and gnmi_port are used for model driven gNMI over gRPC.
    """

    mgmt_host: str
    gnmi_host: str
    gnmi_port: int = 57400


@dataclass
class FabricLocation:
    """
    Fabric location.

    pod groups devices into failure domains and scaling units.
    rack is useful for placement aware planning and blast radius control.
    plane supports multi plane fabrics when you add that later.
    """

    pod: str
    rack: str
    plane: str = "default"


@dataclass
class Link:
    """
    Link from one device interface to a peer.

    peer_device may be a managed device name, or an external placeholder.
    kind controls topology validation semantics.
    """

    local_intf: str
    peer_device: str
    peer_intf: str
    kind: LinkKind = LinkKind.fabric


@dataclass
class DeviceRecord:
    """
    A device record in the inventory store.

    This is the normalized inventory view used by the rest of the system.

    links is populated by inventory sources, such as NetBox cabling.
    capability fields are populated by plugins, such as a port profile plugin.
    """

    name: str
    role: DeviceRole
    identity: DeviceIdentity
    endpoints: DeviceEndpoints
    location: FabricLocation
    links: List[Link] = field(default_factory=list)

    bandwidth_class: Optional[CapabilityClass] = None
    asic_class: Optional[CapabilityClass] = None
    buffer_class: Optional[CapabilityClass] = None
    table_scale_class: Optional[CapabilityClass] = None
    telemetry_class: Optional[CapabilityClass] = None

    role_fitness: Dict[str, CapabilityClass] = field(default_factory=dict)


@dataclass
class IntentChange:
    """
    IntentChange represents a desired state update.

    desired and current are intentionally untyped dictionaries because different sources
    will represent intent differently. The planner is responsible for interpreting it.

    diff_summary is a human readable explanation for audit logs and alerts.
    """

    change_id: str
    scope: str
    desired: Dict[str, Any]
    current: Dict[str, Any]
    diff_summary: str


@dataclass
class ChangeAction:
    """
    A single device action produced by the planner.

    model_paths is a dictionary mapping model path string to desired value.

    Example key:
    /openconfig-network-instance:network-instances/network-instance[name=default]/protocols/...

    We do not include vendor specific CLI in this system.
    """

    device: str
    model_paths: Dict[str, Any]
    reason: str


@dataclass
class VerificationSpec:
    """
    Verification specification.

    checks are deterministic state checks such as BGP established.
    probes are active probes such as ping or tcp connect.

    window_seconds is the observation window for stability after applying the change.
    """

    checks: List[Dict[str, Any]]
    probes: List[Dict[str, Any]]
    window_seconds: int = 60


@dataclass
class RollbackSpec:
    """
    Rollback specification.

    enabled controls whether rollback is allowed.
    triggers describes which verification outcomes trigger rollback.
    """

    enabled: bool = True
    triggers: List[str] = field(default_factory=list)


@dataclass
class ChangePlan:
    """
    ChangePlan is the structured output of the planner.

    risk is a coarse string used by policy gate rules.
    explanation is stored for audit and operator review.
    """

    plan_id: str
    actions: List[ChangeAction]
    verification: VerificationSpec
    rollback: RollbackSpec
    risk: str
    explanation: str
