from datacenter_orchestrator.fabric.graph import (
    build_fabric_graph,
    validate_clos_topology,
)
from datacenter_orchestrator.inventory.store import InventoryStore
from datacenter_orchestrator.core.types import (
    DeviceEndpoints,
    DeviceIdentity,
    DeviceRecord,
    DeviceRole,
    FabricLocation,
    Link,
    LinkKind,
)


def make_device(name: str, role: DeviceRole) -> DeviceRecord:
    """
    Helper to create a minimal DeviceRecord for tests.
    """
    return DeviceRecord(
        name=name,
        role=role,
        identity=DeviceIdentity(
            vendor="demo",
            model="demo",
            os_name="demo",
            os_version="1",
        ),
        endpoints=DeviceEndpoints(
            mgmt_host="10.0.0.1",
            gnmi_host="10.0.0.1",
        ),
        location=FabricLocation(
            pod="pod1",
            rack="r1",
        ),
    )
