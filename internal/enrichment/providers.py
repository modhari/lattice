from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .interfaces import DeviceContextProvider, InterfaceContextProvider


@dataclass(frozen=True)
class DeviceContextRecord:
    device: str
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
class InterfaceContextRecord:
    device: str
    interface: str
    customer_id: Optional[str] = None
    attachment_type: Optional[str] = None
    service_id: Optional[str] = None
    circuit_id: Optional[str] = None
    tenant_id: Optional[str] = None
    peer_device: Optional[str] = None
    peer_interface: Optional[str] = None
    cluster: Optional[str] = None
    availability_zone: Optional[str] = None


class ProviderBundle:
    """
    Simple container for enrichment providers.
    """

    def __init__(
        self,
        device_provider: DeviceContextProvider,
        interface_provider: InterfaceContextProvider,
    ) -> None:
        self.device_provider = device_provider
        self.interface_provider = interface_provider
