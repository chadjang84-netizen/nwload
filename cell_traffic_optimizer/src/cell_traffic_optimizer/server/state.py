"""
Application-wide singleton state — created once at startup, shared via dependency injection.
"""
from __future__ import annotations
import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from ..parser import PacketParser, EventConverter
from ..aggregator import TrafficAggregator, BandMapper
from ..evaluator import CellLoadEvaluator
from ..state_machine import CellStateMachine, DeviceStateMachine
from ..controller import QualityController
from ..controller.onvif_client import OnvifClient
from ..data import DeviceRegistry, CameraRegistry, DeviceCameraMapping, EventStore
from ..config import ConfigParser, ConfigPrinter
from ..pipeline import DataPipeline
from ..models import Configuration

logger = logging.getLogger(__name__)

# 설정 파일 경로 — 프로세스 작업 디렉터리 기준
_CONFIG_FILE = "config.yaml"


def _build_pipeline(config: Configuration, camera_registry: CameraRegistry, mapping: DeviceCameraMapping) -> DataPipeline:

    quality_ctrl = QualityController(
        onvif_client=OnvifClient(),
        camera_registry=camera_registry,
        device_camera_mapping=mapping,
        degraded_ratio=config.degraded_ratio,
        step_up_ratio=config.step_up_ratio,
        max_retries=config.max_onvif_retries,
    )

    return DataPipeline(
        parser=PacketParser(),
        event_converter=EventConverter(arfcn_to_band=BandMapper.arfcn_to_band),
        aggregator=TrafficAggregator(window_seconds=config.sliding_window_seconds),
        evaluator=CellLoadEvaluator(thresholds=config.thresholds),
        cell_sm=CellStateMachine(),
        device_sm=DeviceStateMachine(recovery_cooldown_seconds=config.recovery_cooldown_seconds),
        quality_ctrl=quality_ctrl,
        device_registry=DeviceRegistry(),
    )


_DEFAULT_CONFIG_YAML = """\
thresholds:
  - band: 1
    warning: 8000
    congestion: 16000
    overload_enter: 25000
    overload_exit: 20000
  - band: 3
    warning: 10000
    congestion: 20000
    overload_enter: 30000
    overload_exit: 25000
  - band: 5
    warning: 5000
    congestion: 10000
    overload_enter: 15000
    overload_exit: 12000
  - band: 7
    warning: 12000
    congestion: 24000
    overload_enter: 36000
    overload_exit: 30000
  - band: 8
    warning: 6000
    congestion: 12000
    overload_enter: 18000
    overload_exit: 15000
  - band: 78
    warning: 15000
    congestion: 30000
    overload_enter: 50000
    overload_exit: 40000
degraded_ratio: 0.25
step_up_ratio: 0.50
sliding_window_seconds: 60
recovery_cooldown_seconds: 60
step_up_interval_seconds: 60
max_onvif_retries: 3
"""


def _load_config_yaml() -> str:
    """저장된 설정 파일이 있으면 로드, 없으면 기본값 반환."""
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            # 파싱 가능한지 검증
            ConfigParser.parse(content)
            logger.info("Loaded saved config from %s", _CONFIG_FILE)
            return content
        except Exception as e:
            logger.warning("Failed to load %s (%s), using defaults", _CONFIG_FILE, e)
    return _DEFAULT_CONFIG_YAML


def save_config_yaml(yaml_str: str) -> None:
    """설정을 파일에 저장."""
    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(yaml_str)
        logger.info("Config saved to %s", _CONFIG_FILE)
    except Exception as e:
        logger.error("Failed to save config to %s: %s", _CONFIG_FILE, e)


@dataclass
class AppState:
    config: Configuration
    config_yaml: str
    camera_registry: CameraRegistry
    device_mapping: DeviceCameraMapping
    pipeline: DataPipeline
    event_store: EventStore = field(default_factory=EventStore)
    websocket_clients: set = field(default_factory=set)
    _broadcast_queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    def rebuild_pipeline(self) -> None:
        self.pipeline = _build_pipeline(self.config, self.camera_registry, self.device_mapping)


def create_app_state() -> AppState:
    yaml_str = _load_config_yaml()
    config = ConfigParser.parse(yaml_str)
    camera_registry = CameraRegistry()
    device_mapping = DeviceCameraMapping()
    pipeline = _build_pipeline(config, camera_registry, device_mapping)
    return AppState(
        config=config,
        config_yaml=yaml_str,
        camera_registry=camera_registry,
        device_mapping=device_mapping,
        pipeline=pipeline,
    )
