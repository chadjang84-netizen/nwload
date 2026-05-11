from dataclasses import dataclass, field
from typing import Optional
from .enums import RATType, QualityProfile


@dataclass(frozen=True)
class GroupingKey:
    ecgi: int
    band: int

    def __str__(self) -> str:
        return f"ECGI:{self.ecgi}/Band:{self.band}"


@dataclass(frozen=True)
class RATBlock:
    rat_type: RATType
    plmn_id: bytes
    ecgi: int
    arfcn: int
    timestamp: int
    ul_rb_usage: int


@dataclass(frozen=True)
class ParsedPacket:
    version: int
    message_type: int
    total_length: int
    router_ctn: str
    primary: RATBlock
    secondary: Optional[RATBlock]
    reserved: int


@dataclass(frozen=True)
class RawEvent:
    router_ctn: str
    grouping_key: GroupingKey
    ul_rb_usage: int
    timestamp: float


@dataclass
class GroupStats:
    grouping_key: GroupingKey
    ul_rb_sum: int
    ctn_set: set
    event_count: int


@dataclass(frozen=True)
class ThresholdConfig:
    warning: int
    congestion: int
    overload_enter: int
    overload_exit: int

    def __post_init__(self) -> None:
        if not (self.warning < self.congestion < self.overload_enter):
            raise ValueError(
                f"Threshold order violated: warning({self.warning}) < "
                f"congestion({self.congestion}) < overload_enter({self.overload_enter})"
            )
        if self.overload_exit >= self.overload_enter:
            raise ValueError(
                f"overload_exit({self.overload_exit}) must be < overload_enter({self.overload_enter})"
            )


@dataclass
class CameraDefaultConfig:
    """Cached result of GetVideoEncoderConfiguration for a single camera."""
    bitrate: int
    framerate: int
    resolution: tuple
