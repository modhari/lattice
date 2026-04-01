from __future__ import annotations

from typing import Optional

from .interfaces import DeviceContextProvider, InterfaceContextProvider
from .providers import DeviceContextRecord, InterfaceContextRecord


class InMemoryDeviceContextProvider(DeviceContextProvider):
    def __init__(self, devices: dict[str, DeviceContextRecord]) -> None:
        self.devices = devices

    def get_device_context(self, device: str) -> Optional[DeviceContextRecord]:
        return self.devices.get(device)


class InMemoryInterfaceContextProvider(InterfaceContextProvider):
    def __init__(
        self,
        interfaces: dict[tuple[str, str], InterfaceContextRecord],
    ) -> None:
        self.interfaces = interfaces

    def get_interface_context(
        self,
        device: str,
        interface: str,
    ) -> Optional[InterfaceContextRecord]:
        return self.interfaces.get((device, interface))
