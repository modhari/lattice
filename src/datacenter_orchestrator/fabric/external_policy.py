"""
External connectivity policy.

This module enforces the architecture patterns described:

Border pod or border leaf model
- Internal routing and protocols are isolated from external routing.
- Only border leaves should connect to external networks.

Spine external model for smaller networks
- If spines connect to the external world, all spines must do so.
- Partial external connectivity on a subset of spines breaks the CLOS symmetry and causes congestion.

This policy runs after topology validation and before any configuration is applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from datacenter_orchestrator.core.types import DeviceRole, LinkKind
from datacenter_orchestrator.fabric.graph import FabricGraph
from datacenter_orchestrator.fabric.roles import is_spine_role


@dataclass
class ExternalConnectivityPolicyResult:
    """
    Result of external connectivity validation.

    ok means the policy did not find a blocking error.
    errors are blocking.
    warnings are non blocking but should be reviewed.
    evidence contains structured counts used in alerts.
    """

    ok: bool
    errors: List[str]
    warnings: List[str]
    evidence: Dict[str, object]


def validate_external_connectivity(g: FabricGraph) -> ExternalConnectivityPolicyResult:
    """
    Validate external connectivity architecture.

    Policy rules
    1. If any border_leaf devices exist, treat the architecture as border pod model:
       - At least one border_leaf must have an external link.
       - If spines also have external links, raise a warning because this is mixed mode.

    2. If no border_leaf devices exist, treat the architecture as spine external model:
       - If any spine has an external link, then all spines must have an external link.
       - If only some spines have external links, raise a blocking error.

    What counts as external link
    Any link with kind external, internet, or wan is considered external connectivity.
    """

    errors: List[str] = []
    warnings: List[str] = []
    evidence: Dict[str, object] = {}

    border_leafs = [d for d in g.nodes.values() if d.role == DeviceRole.border_leaf]
    spines = [d for d in g.nodes.values() if is_spine_role(d.role)]

    external_kinds = {LinkKind.external, LinkKind.internet, LinkKind.wan}

    spines_with_external: List[str] = []
    border_leafs_with_external: List[str] = []
    other_with_external: List[str] = []

    for dev in g.nodes.values():
        for e in g.edges_from(dev.name):
            if e.kind in external_kinds:
                if dev.role == DeviceRole.border_leaf:
                    border_leafs_with_external.append(dev.name)
                elif is_spine_role(dev.role):
                    spines_with_external.append(dev.name)
                else:
                    other_with_external.append(dev.name)

    # Border pod model.
    if border_leafs:
        if not border_leafs_with_external:
            errors.append("border_leaf role present but no border_leaf has external connectivity")

        # Mixed mode is not always wrong, but it should be intentional.
        if spines_with_external:
            warnings.append(
                "border_leaf model detected but spines also have external links, verify design intent"
            )

        if other_with_external:
            warnings.append(
                f"non border devices have external links: {sorted(set(other_with_external))}"
            )

    # Spine external model.
    else:
        if spines:
            if 0 < len(set(spines_with_external)) < len(spines):
                errors.append(
                    "partial spine external connectivity detected. "
                    "If spines connect externally, all spines must connect externally."
                )

    evidence["external_connectivity_counts"] = {
        "border_leaf_count": len(border_leafs),
        "spine_count": len(spines),
        "border_leafs_with_external": len(set(border_leafs_with_external)),
        "spines_with_external": len(set(spines_with_external)),
        "other_with_external": len(set(other_with_external)),
    }

    evidence["external_connectivity_nodes"] = {
        "border_leafs_with_external": sorted(set(border_leafs_with_external)),
        "spines_with_external": sorted(set(spines_with_external)),
        "other_with_external": sorted(set(other_with_external)),
    }

    ok = len(errors) == 0
    return ExternalConnectivityPolicyResult(ok=ok, errors=errors, warnings=warnings, evidence=evidence)
