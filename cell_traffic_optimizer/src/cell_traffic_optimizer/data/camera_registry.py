import logging
from typing import Optional
from cryptography.fernet import Fernet
from ..models import CameraRegistryEntry

logger = logging.getLogger(__name__)


class CameraRegistry:

    def __init__(self, encryption_key: Optional[bytes] = None):
        self._registry: dict = {}
        self._fernet = Fernet(encryption_key or Fernet.generate_key())

    def register(
        self,
        camera_id: str,
        ip_address: str,
        onvif_port: int,
        username: str,
        password: str,
        profile_token: str,
    ) -> CameraRegistryEntry:
        encrypted = self._fernet.encrypt(password.encode())
        entry = CameraRegistryEntry(
            camera_id=camera_id,
            ip_address=ip_address,
            onvif_port=onvif_port,
            username=username,
            encrypted_password=encrypted,
            profile_token=profile_token,
            is_reachable=True,
        )
        self._registry[camera_id] = entry
        return entry

    def get(self, camera_id: str) -> Optional[CameraRegistryEntry]:
        return self._registry.get(camera_id)

    def get_password(self, camera_id: str) -> Optional[str]:
        entry = self._registry.get(camera_id)
        if entry is None:
            return None
        return self._fernet.decrypt(entry.encrypted_password).decode()

    def mark_unreachable(self, camera_id: str) -> None:
        if camera_id in self._registry:
            self._registry[camera_id].is_reachable = False
            logger.warning("Camera %s marked as unreachable", camera_id)

    def mark_reachable(self, camera_id: str) -> None:
        if camera_id in self._registry:
            self._registry[camera_id].is_reachable = True

    def update(
        self,
        camera_id: str,
        ip_address: str,
        onvif_port: int,
        username: str,
        password: Optional[str],
        profile_token: str,
    ) -> Optional[CameraRegistryEntry]:
        entry = self._registry.get(camera_id)
        if entry is None:
            return None
        entry.ip_address = ip_address
        entry.onvif_port = onvif_port
        entry.username = username
        if password:
            entry.encrypted_password = self._fernet.encrypt(password.encode())
        entry.profile_token = profile_token
        entry.is_reachable = True
        return entry

    def remove(self, camera_id: str) -> bool:
        if camera_id in self._registry:
            del self._registry[camera_id]
            return True
        return False

    def all(self) -> list:
        return list(self._registry.values())
