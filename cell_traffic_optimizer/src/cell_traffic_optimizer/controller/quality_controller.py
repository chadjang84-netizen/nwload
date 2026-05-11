import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol
from ..models import QualityProfile
from ..data.camera_registry import CameraRegistry
from ..data.device_camera_mapping import DeviceCameraMapping

logger = logging.getLogger(__name__)

MAX_COMMAND_LOG = 500


class ONVIFClient(Protocol):

    def get_video_encoder_configuration(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        profile_token: str,
    ) -> dict:
        """Return dict with keys: bitrate (int), framerate (int), resolution (tuple)."""
        ...

    def set_video_encoder_configuration(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        profile_token: str,
        bitrate: int,
        framerate: int,
        resolution: tuple,
    ) -> bool:
        ...


@dataclass
class CommandResult:
    camera_id: str
    success: bool
    error: str = ""


@dataclass
class CommandLogEntry:
    timestamp: str
    camera_id: str
    router_ctn: str
    command: str        # "GetVideoEncoderConfiguration" | "SetVideoEncoderConfiguration"
    profile: str        # "NORMAL" | "DEGRADED" | "STEP_UP"
    bitrate: int
    framerate: int
    resolution: tuple
    success: bool
    error: str = ""


class QualityController:

    def __init__(
        self,
        onvif_client: ONVIFClient,
        camera_registry: CameraRegistry,
        device_camera_mapping: DeviceCameraMapping,
        degraded_ratio: float = 0.25,
        step_up_ratio: float = 0.50,
        max_retries: int = 3,
    ):
        self._client = onvif_client
        self._camera_registry = camera_registry
        self._mapping = device_camera_mapping
        self._degraded_ratio = degraded_ratio
        self._step_up_ratio = step_up_ratio
        self._max_retries = max_retries
        self.command_log: list[CommandLogEntry] = []
        # camera_id -> {"bitrate": int, "framerate": int, "resolution": tuple}
        self._default_configs: dict[str, dict] = {}

    def _log(self, entry: CommandLogEntry) -> None:
        self.command_log.insert(0, entry)
        if len(self.command_log) > MAX_COMMAND_LOG:
            self.command_log = self.command_log[:MAX_COMMAND_LOG]

    def prefetch_camera_defaults(self, ctn: str) -> None:
        """WARNING 진입 시 호출 — 해당 CTN 매핑 카메라의 기본값을 미리 GET해 캐시한다."""
        camera_ids = self._mapping.get_camera_ids(ctn)
        for camera_id in camera_ids:
            if camera_id not in self._default_configs:
                self._fetch_and_cache_default(camera_id, ctn)

    def is_mapped(self, ctn: str) -> bool:
        """CTN에 카메라가 매핑되어 있는지 확인한다."""
        return bool(self._mapping.get_camera_ids(ctn))

    def apply_profile(self, ctn: str, profile: QualityProfile) -> list:
        """OVERLOAD/step_up 시 호출 — 캐시된 기본값 기반으로 bitrate 비율 적용."""
        camera_ids = self._mapping.get_camera_ids(ctn)
        if not camera_ids:
            logger.warning("No cameras mapped for CTN %s — cannot apply %s profile", ctn, profile.value)
            self._log(CommandLogEntry(
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
                camera_id="",
                router_ctn=ctn,
                command="SetVideoEncoderConfiguration",
                profile=profile.value,
                bitrate=0, framerate=0, resolution=(0, 0),
                success=False,
                error=f"No cameras mapped for CTN {ctn}",
            ))
            return []

        results = []
        for camera_id in camera_ids:
            # 캐시 없으면 fallback GET
            if camera_id not in self._default_configs:
                self._fetch_and_cache_default(camera_id, ctn)

            default = self._default_configs.get(camera_id)
            if default is None:
                results.append(CommandResult(camera_id=camera_id, success=False, error="No default config"))
                continue

            target_bitrate = self._calc_bitrate(default["bitrate"], profile)
            result = self._apply_to_camera(
                camera_id, ctn, profile.value,
                target_bitrate, default["framerate"], default["resolution"],
            )
            results.append(result)

        return results

    def _calc_bitrate(self, default_bitrate: int, profile: QualityProfile) -> int:
        if profile == QualityProfile.DEGRADED:
            return max(1, int(default_bitrate * self._degraded_ratio))
        elif profile == QualityProfile.STEP_UP:
            return max(1, int(default_bitrate * self._step_up_ratio))
        else:  # NORMAL
            return default_bitrate

    def _fetch_and_cache_default(self, camera_id: str, ctn: str) -> None:
        entry = self._camera_registry.get(camera_id)
        if entry is None:
            return
        password = self._camera_registry.get_password(camera_id)
        try:
            config = self._client.get_video_encoder_configuration(
                ip=entry.ip_address,
                port=entry.onvif_port,
                username=entry.username,
                password=password,
                profile_token=entry.profile_token,
            )
            self._default_configs[camera_id] = {
                "bitrate":    config["bitrate"],
                "framerate":  config["framerate"],
                "resolution": tuple(config["resolution"]),
            }
            self._log(CommandLogEntry(
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
                camera_id=camera_id,
                router_ctn=ctn,
                command="GetVideoEncoderConfiguration",
                profile="NORMAL",
                bitrate=config["bitrate"],
                framerate=config["framerate"],
                resolution=tuple(config["resolution"]),
                success=True,
            ))
            logger.info("Camera %s default config cached: %dbps %dfps %s",
                        camera_id, config["bitrate"], config["framerate"], config["resolution"])
        except Exception as e:
            logger.warning("Camera %s GET failed: %s", camera_id, e)
            self._log(CommandLogEntry(
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
                camera_id=camera_id,
                router_ctn=ctn,
                command="GetVideoEncoderConfiguration",
                profile="NORMAL",
                bitrate=0, framerate=0, resolution=(0, 0),
                success=False, error=str(e),
            ))

    def _apply_to_camera(
        self,
        camera_id: str,
        ctn: str,
        profile_name: str,
        bitrate: int,
        framerate: int,
        resolution: tuple,
    ) -> CommandResult:
        entry = self._camera_registry.get(camera_id)
        if entry is None:
            self._log(CommandLogEntry(
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
                camera_id=camera_id, router_ctn=ctn,
                command="SetVideoEncoderConfiguration", profile=profile_name,
                bitrate=bitrate, framerate=framerate, resolution=resolution,
                success=False, error="Camera not found in registry",
            ))
            return CommandResult(camera_id=camera_id, success=False, error="Camera not found in registry")

        password = self._camera_registry.get_password(camera_id)

        for attempt in range(1, self._max_retries + 1):
            try:
                ok = self._client.set_video_encoder_configuration(
                    ip=entry.ip_address,
                    port=entry.onvif_port,
                    username=entry.username,
                    password=password,
                    profile_token=entry.profile_token,
                    bitrate=bitrate,
                    framerate=framerate,
                    resolution=resolution,
                )
                if ok:
                    logger.info("Camera %s SET %s %dbps (attempt %d)", camera_id, profile_name, bitrate, attempt)
                    self._log(CommandLogEntry(
                        timestamp=datetime.now(tz=timezone.utc).isoformat(),
                        camera_id=camera_id, router_ctn=ctn,
                        command="SetVideoEncoderConfiguration", profile=profile_name,
                        bitrate=bitrate, framerate=framerate, resolution=resolution,
                        success=True,
                    ))
                    return CommandResult(camera_id=camera_id, success=True)
            except Exception as e:
                logger.warning("Camera %s attempt %d failed: %s", camera_id, attempt, e)

        logger.error("Camera %s all %d retries failed", camera_id, self._max_retries)
        self._log(CommandLogEntry(
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            camera_id=camera_id, router_ctn=ctn,
            command="SetVideoEncoderConfiguration", profile=profile_name,
            bitrate=bitrate, framerate=framerate, resolution=resolution,
            success=False, error=f"Failed after {self._max_retries} retries",
        ))
        return CommandResult(camera_id=camera_id, success=False, error=f"Failed after {self._max_retries} retries")
