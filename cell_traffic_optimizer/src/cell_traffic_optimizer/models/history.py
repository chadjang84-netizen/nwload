from dataclasses import dataclass
from typing import Optional
from .enums import DeviceState, DeviceAction, QualityProfile, CellState
from .core import GroupingKey


@dataclass
class DeviceHistory:
    router_ctn: str
    current_state: DeviceState
    last_action: Optional[DeviceAction]
    last_action_time: Optional[float]
    cooldown_start_time: Optional[float]
    current_profile: QualityProfile


@dataclass
class CellStabilityRecord:
    grouping_key: GroupingKey
    current_state: CellState
    state_entered_at: float
    normal_duration_seconds: float
