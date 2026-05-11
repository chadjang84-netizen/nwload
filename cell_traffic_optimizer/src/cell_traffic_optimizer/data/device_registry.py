from typing import Optional
from ..models import DeviceRegistryEntry


class DeviceRegistry:

    def __init__(self):
        self._registry: dict = {}

    def register_or_update(self, router_ctn: str, timestamp: float) -> DeviceRegistryEntry:
        if router_ctn in self._registry:
            self._registry[router_ctn].last_packet_time = timestamp
        else:
            self._registry[router_ctn] = DeviceRegistryEntry(
                router_ctn=router_ctn,
                is_registered=True,
                last_packet_time=timestamp,
                registered_at=timestamp,
            )
        return self._registry[router_ctn]

    def get(self, router_ctn: str) -> Optional[DeviceRegistryEntry]:
        return self._registry.get(router_ctn)

    def is_registered(self, router_ctn: str) -> bool:
        return router_ctn in self._registry

    def all(self) -> list:
        return list(self._registry.values())
