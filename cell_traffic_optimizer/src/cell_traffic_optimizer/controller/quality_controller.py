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
        use_tls: bool = False,
        media_service_path: str = "/onvif/media",
    ) -> dict:
        """Return dict with keys: bitrate (int), framerate (int), resolution (tuple)."""
        ...

    def get_video_encoder_configurations(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = False,
        media_service_path: str = "/onvif/media",
    ) -> list:
        """Return a list of available VideoEncoderConfiguration tokens."""
        ...

    def resolve_token(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        profile_token: str,
        use_tls: bool = False,
        media_service_path: str = "/onvif/media",
    ) -> str:
        """Return profile_token if given, else auto-discover the first encoder token."""
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
        use_tls: bool = False,
        media_service_path: str = "/onvif/media",
        video_codec: str = "H264",
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
        # camera_id -> 자동 발견(또는 입력) 후 확정된 VideoEncoderConfiguration token
        self._resolved_tokens: dict[str, str] = {}

    def _log(self, entry: CommandLogEntry) -> None:
        self.command_log.insert(0, entry)
        if len(self.command_log) > MAX_COMMAND_LOG:
            self.command_log = self.command_log[:MAX_COMMAND_LOG]

    def _resolve_token(self, camera_id: str, entry, password: str) -> str:
        """카메라의 VideoEncoderConfiguration token을 결정한다(camera_id별 캐시).

        entry.profile_token이 있으면 그대로, 비어 있으면 ONVIF로 첫 토큰을 자동 발견한다.
        GET 캐싱·drift 체크·SET이 모두 동일한 토큰을 쓰도록 캐시한다.
        """
        cached = self._resolved_tokens.get(camera_id)
        if cached:
            return cached
        token = self._client.resolve_token(
            ip=entry.ip_address,
            port=entry.onvif_port,
            username=entry.username,
            password=password,
            profile_token=entry.profile_token,
            use_tls=getattr(entry, "use_tls", False),
            media_service_path=getattr(entry, "media_service_path", "/onvif/media"),
        )
        self._resolved_tokens[camera_id] = token
        return token

    def prefetch_camera_defaults(self, ctn: str) -> None:
        """WARNING 진입 시 호출 — 해당 CTN 매핑 카메라의 기본값을 미리 GET해 캐시한다."""
        camera_ids = self._mapping.get_camera_ids(ctn)
        for camera_id in camera_ids:
            if camera_id not in self._default_configs:
                self._fetch_and_cache_default(camera_id, ctn)

    def is_mapped(self, ctn: str) -> bool:
        """CTN에 카메라가 매핑되어 있는지 확인한다."""
        return bool(self._mapping.get_camera_ids(ctn))

    def is_already_at_default(self, ctn: str, tolerance: float = 0.9) -> bool:
        """매핑된 모든 카메라의 실제 bitrate가 캐시된 원본값 근처(>= 원본 × tolerance)인지
        ONVIF GET으로 확인한다. 카메라 재부팅 등으로 NVRAM 원본값이 복원된 경우를
        감지해 잘못된 step_up SET을 방지하기 위한 가드.

        반환값:
            True  - 모든 카메라가 이미 원본 상태 → SET 불필요
            False - 한 대라도 저화질 상태이거나 GET 실패 → 정상 step_up 흐름 진행
        """
        camera_ids = self._mapping.get_camera_ids(ctn)
        if not camera_ids:
            return False
        for camera_id in camera_ids:
            entry = self._camera_registry.get(camera_id)
            default = self._default_configs.get(camera_id)
            if entry is None or default is None:
                return False
            password = self._camera_registry.get_password(camera_id)
            try:
                token = self._resolve_token(camera_id, entry, password)
                actual = self._client.get_video_encoder_configuration(
                    ip=entry.ip_address,
                    port=entry.onvif_port,
                    username=entry.username,
                    password=password,
                    profile_token=token,
                    use_tls=getattr(entry, "use_tls", False),
                    media_service_path=getattr(entry, "media_service_path", "/onvif/media"),
                )
            except Exception as e:
                logger.warning("Camera %s GET (drift check) failed: %s", camera_id, e)
                return False
            if actual["bitrate"] < default["bitrate"] * tolerance:
                logger.debug(
                    "Camera %s still at low bitrate (%d < %d * %.2f) — step_up needed",
                    camera_id, actual["bitrate"], default["bitrate"], tolerance,
                )
                return False
        logger.info("CTN %s cameras already at default bitrate (reboot or external reset detected)", ctn)
        return True

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
            token = self._resolve_token(camera_id, entry, password)
            config = self._client.get_video_encoder_configuration(
                ip=entry.ip_address,
                port=entry.onvif_port,
                username=entry.username,
                password=password,
                profile_token=token,
                use_tls=getattr(entry, "use_tls", False),
                media_service_path=getattr(entry, "media_service_path", "/onvif/media"),
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

        try:
            token = self._resolve_token(camera_id, entry, password)
        except Exception as e:
            logger.warning("Camera %s token resolve (SET) failed: %s", camera_id, e)
            self._log(CommandLogEntry(
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
                camera_id=camera_id, router_ctn=ctn,
                command="SetVideoEncoderConfiguration", profile=profile_name,
                bitrate=bitrate, framerate=framerate, resolution=resolution,
                success=False, error=str(e),
            ))
            return CommandResult(camera_id=camera_id, success=False, error=str(e))

        for attempt in range(1, self._max_retries + 1):
            try:
                ok = self._client.set_video_encoder_configuration(
                    ip=entry.ip_address,
                    port=entry.onvif_port,
                    username=entry.username,
                    password=password,
                    profile_token=token,
                    bitrate=bitrate,
                    framerate=framerate,
                    resolution=resolution,
                    use_tls=getattr(entry, "use_tls", False),
                    media_service_path=getattr(entry, "media_service_path", "/onvif/media"),
                    video_codec=getattr(entry, "video_codec", "H264"),
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
