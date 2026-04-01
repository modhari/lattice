from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from .models import EnrichmentData, EnrichmentKey


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


class DeviceContextProvider(ABC):
    @abstractmethod
    def get_device_context(self, device: str) -> Optional[DeviceContextRecord]:
        raise NotImplementedError


class InterfaceContextProvider(ABC):
    @abstractmethod
    def get_interface_context(
        self,
        device: str,
        interface: str,
    ) -> Optional[InterfaceContextRecord]:
        raise NotImplementedError


class EnrichmentProvider(ABC):
    @abstractmethod
    def resolve(self, key: EnrichmentKey) -> EnrichmentData:
        raise NotImplementedError
