from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeviceRegistryEntry:
    router_ctn: str
    is_registered: bool
    last_packet_time: float
    registered_at: float


@dataclass
class CameraRegistryEntry:
    camera_id: str
    ip_address: str
    onvif_port: int
    username: str
    encrypted_password: bytes
    profile_token: str
    is_reachable: bool = True


@dataclass
class DeviceCameraMappingEntry:
    router_ctn: str
    camera_ids: list = field(default_factory=list)
