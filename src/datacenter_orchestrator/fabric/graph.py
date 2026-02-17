"""
Fabric graph.

This module converts normalized inventory records into a graph representation
that validators and planners can reason about.

Design goals
1. Keep this deterministic and simple.
2. Avoid any vendor specific logic here.
3. Make it easy to attach evidence to validation outputs.

What is a FabricGraph
- nodes: device name -> DeviceRecord
- adjacency: device name -> list of edges

Edges are directional in our representation, but physical links are usually bidirectional.
The builder adds edges in both directions when the peer is a managed device.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from datacenter_orchestrator.core.types import DeviceRecord, Link, LinkKind
from datacenter_orchestrator.inventory.store import InventoryStore
from datacenter_orchestrator.fabric.roles import is_leaf_role, is_spine_role, is_super_spine_role


@dataclass(frozen=True)
class GraphEdge:
    """
    GraphEdge represents one adjacency entry.

    We carry:
    - local interface
    - peer device name
    - peer interface
    - link kind for semantics

    This is intentionally similar to Link, but separated so we can evolve graph logic
    without changing the inventory layer.
    """

    local_intf: str
    peer_device: str
    peer_intf: str
    kind: LinkKind


@dataclass
class FabricGraph:
    """
    FabricGraph is the in memory topology.

    nodes maps name to DeviceRecord.
    adjacency maps name to a list of GraphEdge for that node.
    """

    nodes: Dict[str, DeviceRecord]
    adjacency: Dict[str, List[GraphEdge]] = field(default_factory=dict)

    def edges_from(self, device: str) -> List[GraphEdge]:
        """Return the outgoing edges for a device name."""
        return self.adjacency.get(device, [])

    def has_device(self, device: str) -> bool:
        """Return True if a device name exists in nodes."""
        return device in self.nodes


def build_fabric_graph(store: InventoryStore) -> FabricGraph:
    """
    Build a FabricGraph from InventoryStore.

    Behavior
    1. For each DeviceRecord, add its links.
    2. If a link peer_device exists in inventory, add reverse edge as well.
       This keeps the graph usable even if only one direction is described by a source.
    3. If peer_device is not managed, keep it as an external edge only.
    """

    nodes = {d.name: d for d in store.all()}
    g = FabricGraph(nodes=nodes, adjacency={})

    # Initialize adjacency keys for all managed nodes.
    for name in nodes:
        g.adjacency[name] = []

    # Add edges based on the normalized Link list.
    for dev in store.all():
        for ln in dev.links:
            g.adjacency[dev.name].append(
                GraphEdge(
                    local_intf=ln.local_intf,
                    peer_device=ln.peer_device,
                    peer_intf=ln.peer_intf,
                    kind=ln.kind,
                )
            )

            # If the peer is a managed device, add reverse edge as well.
            if ln.peer_device in nodes:
                # We do not attempt to de duplicate or reconcile conflicting info here.
                # The validator will detect inconsistent links if needed.
                g.adjacency[ln.peer_device].append(
                    GraphEdge(
                        local_intf=ln.peer_intf,
                        peer_device=dev.name,
                        peer_intf=ln.local_intf,
                        kind=ln.kind,
                    )
                )

    return g


@dataclass
class TopologyValidationResult:
    """
    Result of topology validation.

    ok means no blocking errors.
    errors are blocking.
    warnings are non blocking but important signals.
    evidence is a structured dictionary that can be inserted into alerts.
    """

    ok: bool
    errors: List[str]
    warnings: List[str]
    evidence: Dict[str, object]


def validate_clos_topology(g: FabricGraph) -> TopologyValidationResult:
    """
    Validate basic CLOS invariants.

    This validator is intentionally conservative.
    It does not attempt to validate every possible deployment.
    It validates the invariants that keep the orchestrator safe.

    Validations
    1. Every leaf like device must have at least two fabric uplinks to spine like devices.
       This enforces redundancy and matches common CLOS practice.
    2. Spine like devices should not connect directly to servers or unknown leafs via fabric links.
       We only validate that their fabric neighbors are leaf like or super spine.
    3. If super spines exist:
       - super spines should connect only to spines via fabric links
       - spines may connect to super spines via fabric links
    4. We record counts and neighbor distribution for evidence.

    We do not validate MLAG peer links here, except that they should not be counted as fabric uplinks.
    """

    errors: List[str] = []
    warnings: List[str] = []
    evidence: Dict[str, object] = {}

    leaf_names: List[str] = []
    spine_names: List[str] = []
    super_spine_names: List[str] = []

    # Classify devices by role.
    for dev in g.nodes.values():
        if is_leaf_role(dev.role):
            leaf_names.append(dev.name)
        elif is_spine_role(dev.role):
            spine_names.append(dev.name)
        elif is_super_spine_role(dev.role):
            super_spine_names.append(dev.name)

    evidence["device_counts"] = {
        "leaf_like": len(leaf_names),
        "spine_like": len(spine_names),
        "super_spine": len(super_spine_names),
    }

    # Helper to check whether a peer device is a managed node and return its role class.
    def peer_role_class(peer: str) -> Optional[str]:
        if peer not in g.nodes:
            return None
        role = g.nodes[peer].role
        if is_leaf_role(role):
            return "leaf_like"
        if is_spine_role(role):
            return "spine_like"
        if is_super_spine_role(role):
            return "super_spine"
        return "unknown"

    # Validation 1: leaf uplink redundancy.
    leaf_uplink_evidence: Dict[str, object] = {}
    for leaf in leaf_names:
        fabric_uplinks_to_spines = 0
        fabric_neighbors: Set[str] = set()

        for e in g.edges_from(leaf):
            # Only count fabric links for uplink redundancy.
            if e.kind != LinkKind.fabric:
                continue

            fabric_neighbors.add(e.peer_device)

            # Count uplinks that terminate on spine like devices.
            if peer_role_class(e.peer_device) == "spine_like":
                fabric_uplinks_to_spines += 1

        leaf_uplink_evidence[leaf] = {
            "fabric_uplinks_to_spines": fabric_uplinks_to_spines,
            "fabric_neighbor_count": len(fabric_neighbors),
        }

        if fabric_uplinks_to_spines < 2:
            errors.append(
                f"leaf like device {leaf} has only {fabric_uplinks_to_spines} fabric uplinks to spines, require at least 2"
            )

    evidence["leaf_uplinks"] = leaf_uplink_evidence

    # Validation 2: spine neighbor roles.
    spine_neighbor_evidence: Dict[str, object] = {}
    for spine in spine_names:
        bad_fabric_neighbors: List[str] = []
        fabric_neighbor_roles: Dict[str, int] = {"leaf_like": 0, "spine_like": 0, "super_spine": 0, "unknown": 0}

        for e in g.edges_from(spine):
            if e.kind != LinkKind.fabric:
                continue

            cls = peer_role_class(e.peer_device)
            if cls is None:
                # A fabric link to unknown external peer is suspicious.
                fabric_neighbor_roles["unknown"] += 1
                bad_fabric_neighbors.append(e.peer_device)
            else:
                fabric_neighbor_roles[cls] = fabric_neighbor_roles.get(cls, 0) + 1

                # In a two tier design, spines should connect to leaf like devices.
                # In a three tier design, spines may also connect to super spines.
                if cls not in {"leaf_like", "super_spine"}:
                    bad_fabric_neighbors.append(e.peer_device)

        spine_neighbor_evidence[spine] = {
            "fabric_neighbor_roles": fabric_neighbor_roles,
            "bad_fabric_neighbors": bad_fabric_neighbors,
        }

        if bad_fabric_neighbors:
            warnings.append(
                f"spine like device {spine} has fabric neighbors that are unexpected: {sorted(set(bad_fabric_neighbors))}"
            )

    evidence["spine_neighbors"] = spine_neighbor_evidence

    # Validation 3: super spine constraints if present.
    if super_spine_names:
        super_spine_evidence: Dict[str, object] = {}

        for ss in super_spine_names:
            bad_neighbors: List[str] = []
            spine_neighbor_count = 0

            for e in g.edges_from(ss):
                if e.kind != LinkKind.fabric:
                    continue

                cls = peer_role_class(e.peer_device)
                if cls != "spine_like":
                    bad_neighbors.append(e.peer_device)
                else:
                    spine_neighbor_count += 1

            super_spine_evidence[ss] = {"spine_neighbor_count": spine_neighbor_count, "bad_neighbors": bad_neighbors}

            if bad_neighbors:
                errors.append(
                    f"super spine {ss} has fabric neighbors that are not spines: {sorted(set(bad_neighbors))}"
                )

            if spine_neighbor_count == 0:
                errors.append(f"super spine {ss} has no spine neighbors via fabric links")

        evidence["super_spine_neighbors"] = super_spine_evidence

    ok = len(errors) == 0
    return TopologyValidationResult(ok=ok, errors=errors, warnings=warnings, evidence=evidence)
