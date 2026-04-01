from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional


LabelMode = Literal["metrics_safe", "rich"]


@dataclass(frozen=True)
class EnrichmentKey:
    """
    Primary lookup key used to resolve enrichment context.

    Most interface related enrichment will use:
    - device
    - interface

    Some workflows may later use:
    - subinterface
    - lag
    - network_instance
    - circuit_id
    """

    device: str
    interface: Optional[str] = None
    subinterface: Optional[str] = None
    lag: Optional[str] = None
    network_instance: Optional[str] = None
    circuit_id: Optional[str] = None
    customer_attachment_id: Optional[str] = None


@dataclass(frozen=True)
class InfrastructureContext:
    datacenter: Optional[str] = None
    pop: Optional[str] = None
    region: Optional[str] = None
    site_code: Optional[str] = None
    role: Optional[str] = None
    topology_role: Optional[str] = None
    fabric: Optional[str] = None
    pod: Optional[str] = None
    rack: Optional[str] = None


@dataclass(frozen=True)
class CustomerContext:
    customer_id: Optional[str] = None
    attachment_type: Optional[str] = None
    service_id: Optional[str] = None
    circuit_id: Optional[str] = None
    tenant_id: Optional[str] = None


@dataclass(frozen=True)
class TopologyContext:
    peer_device: Optional[str] = None
    peer_interface: Optional[str] = None
    cluster: Optional[str] = None
    availability_zone: Optional[str] = None


@dataclass(frozen=True)
class EnrichmentData:
    infrastructure: InfrastructureContext = field(default_factory=InfrastructureContext)
    customer: CustomerContext = field(default_factory=CustomerContext)
    topology: TopologyContext = field(default_factory=TopologyContext)

    def to_flat_labels(self, mode: LabelMode = "metrics_safe") -> dict[str, str]:
        """
        Returns a flat label map.

        metrics_safe:
            Low cardinality labels intended for Prometheus.

        rich:
            Broader label map for controlled non Prometheus use cases.
        """
        labels: dict[str, str] = {}

        infra = asdict(self.infrastructure)
        cust = asdict(self.customer)
        topo = asdict(self.topology)

        metrics_safe_fields = {
            "datacenter",
            "pop",
            "region",
            "site_code",
            "role",
            "topology_role",
            "fabric",
            "pod",
            "customer_id",
            "attachment_type",
        }

        rich_fields = {
            "datacenter",
            "pop",
            "region",
            "site_code",
            "role",
            "topology_role",
            "fabric",
            "pod",
            "rack",
            "customer_id",
            "attachment_type",
            "service_id",
            "circuit_id",
            "tenant_id",
            "cluster",
            "availability_zone",
            "peer_device",
            "peer_interface",
        }

        allowed = metrics_safe_fields if mode == "metrics_safe" else rich_fields

        for source in (infra, cust, topo):
            for key, value in source.items():
                if key in allowed and value is not None:
                    labels[key] = str(value)

        return labels

    def to_rich_context(self) -> dict[str, Any]:
        """
        Rich structured context for event, object, and audit exports.
        """
        return {
            "infrastructure": asdict(self.infrastructure),
            "customer": asdict(self.customer),
            "topology": asdict(self.topology),
        }


@dataclass
class NormalizedMetric:
    name: str
    value: float | int
    labels: dict[str, str]
    timestamp_ms: Optional[int] = None

    def copy(self) -> "NormalizedMetric":
        return NormalizedMetric(
            name=self.name,
            value=self.value,
            labels=dict(self.labels),
            timestamp_ms=self.timestamp_ms,
        )


@dataclass
class EnrichedMetric:
    name: str
    value: float | int
    labels: dict[str, str]
    timestamp_ms: Optional[int] = None
    enrichment: dict[str, Any] = field(default_factory=dict)

    def to_prometheus_sample(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "labels": self.labels,
            "timestamp_ms": self.timestamp_ms,
        }


@dataclass
class NormalizedEvent:
    event_type: str
    severity: str
    attributes: dict[str, Any]
    timestamp_ms: Optional[int] = None


@dataclass
class EnrichedEvent:
    event_type: str
    severity: str
    attributes: dict[str, Any]
    timestamp_ms: Optional[int] = None
    enrichment: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedObject:
    object_type: str
    object_id: str
    attributes: dict[str, Any]


@dataclass
class EnrichedObject:
    object_type: str
    object_id: str
    attributes: dict[str, Any]
    enrichment: dict[str, Any] = field(default_factory=dict)
