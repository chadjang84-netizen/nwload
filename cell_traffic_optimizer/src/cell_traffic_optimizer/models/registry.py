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
    # ONVIF endpoint 커스터마이즈 (제조사별 차이 흡수)
    use_tls: bool = False                          # False=http, True=https
    media_service_path: str = "/onvif/media"       # 카메라마다 다를 수 있음
    video_codec: str = "H264"                      # "H264" or "H265"


@dataclass
class DeviceCameraMappingEntry:
    router_ctn: str
    camera_ids: list = field(default_factory=list)
