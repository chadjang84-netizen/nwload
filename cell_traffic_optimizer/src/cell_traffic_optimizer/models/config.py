from dataclasses import dataclass, field
from .core import ThresholdConfig


@dataclass
class Configuration:
    thresholds: dict            # band (int) -> ThresholdConfig
    degraded_ratio: float = 0.25   # bitrate multiplier for DEGRADED profile
    step_up_ratio: float = 0.50    # bitrate multiplier for STEP_UP profile
    sliding_window_seconds: int = 300
    recovery_cooldown_seconds: int = 3600
    step_up_interval_seconds: int = 3600
    supported_version: int = 1
    supported_message_type: int = 1
    max_onvif_retries: int = 3
