from enum import Enum


class RATType(Enum):
    NONE = 0x00
    LTE_PRIMARY = 0x01
    NR = 0x02
    REDCAP = 0x03


class CellState(Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CONGESTION = "CONGESTION"
    OVERLOAD = "OVERLOAD"


class DeviceState(Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    RECOVERY_PENDING = "RECOVERY_PENDING"
    UNMANAGED = "UNMANAGED"  # ONVIF 매핑 없어서 제어 불가


class QualityProfile(Enum):
    DEGRADED = "DEGRADED"   # bitrate x degraded_ratio (e.g. 25%)
    STEP_UP  = "STEP_UP"    # bitrate x step_up_ratio  (e.g. 50%, mid-recovery)
    NORMAL   = "NORMAL"     # restore to camera default bitrate


class DeviceAction(Enum):
    DOWNGRADE = "DOWNGRADE"
    STEP_UP = "STEP_UP"
    RESTORE = "RESTORE"
    UNMANAGED = "UNMANAGED"
