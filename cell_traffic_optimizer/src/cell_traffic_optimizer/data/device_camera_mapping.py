import logging
from typing import Optional
from ..models import DeviceCameraMappingEntry

logger = logging.getLogger(__name__)


class DeviceCameraMapping:

    def __init__(self):
        self._mapping: dict = {}

    def add_mapping(self, router_ctn: str, camera_id: str, timestamp: float) -> None:
        if router_ctn not in self._mapping:
            self._mapping[router_ctn] = DeviceCameraMappingEntry(router_ctn=router_ctn, camera_ids=[])
        entry = self._mapping[router_ctn]
        if camera_id not in entry.camera_ids:
            old = list(entry.camera_ids)
            entry.camera_ids.append(camera_id)
            logger.info("Mapping added: %s -> %s (was: %s, now: %s) at %.0f",
                        router_ctn, camera_id, old, entry.camera_ids, timestamp)

    def remove_mapping(self, router_ctn: str, camera_id: str, timestamp: float) -> bool:
        entry = self._mapping.get(router_ctn)
        if entry is None or camera_id not in entry.camera_ids:
            return False
        old = list(entry.camera_ids)
        entry.camera_ids.remove(camera_id)
        logger.info("Mapping removed: %s -> %s (was: %s, now: %s) at %.0f",
                    router_ctn, camera_id, old, entry.camera_ids, timestamp)
        return True

    def get_camera_ids(self, router_ctn: str) -> list:
        entry = self._mapping.get(router_ctn)
        if entry is None:
            return []
        return list(entry.camera_ids)

    def get_entry(self, router_ctn: str) -> Optional[DeviceCameraMappingEntry]:
        return self._mapping.get(router_ctn)

    def all(self) -> list:
        return list(self._mapping.values())
