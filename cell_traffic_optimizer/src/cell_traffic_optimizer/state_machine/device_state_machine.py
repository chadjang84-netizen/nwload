import logging
from dataclasses import dataclass
from typing import Optional
from ..models import DeviceState, QualityProfile, DeviceAction, DeviceHistory

logger = logging.getLogger(__name__)

_PROFILE_STEP_UP = {
    QualityProfile.DEGRADED: QualityProfile.STEP_UP,
    QualityProfile.STEP_UP:  QualityProfile.NORMAL,
}


@dataclass
class DeviceActionResult:
    success: bool
    router_ctn: str
    previous_state: DeviceState
    new_state: DeviceState
    previous_profile: QualityProfile
    new_profile: QualityProfile
    action: Optional[DeviceAction]
    timestamp: float
    message: str = ""


class DeviceStateMachine:

    def __init__(self, recovery_cooldown_seconds: int = 3600):
        self._recovery_cooldown_seconds = recovery_cooldown_seconds
        self._states: dict = {}
        self._profiles: dict = {}
        self._histories: dict = {}

    def _get_state(self, ctn: str) -> DeviceState:
        return self._states.get(ctn, DeviceState.NORMAL)

    def _get_profile(self, ctn: str) -> QualityProfile:
        return self._profiles.get(ctn, QualityProfile.NORMAL)  # NORMAL = camera default

    def degrade(self, ctn: str, timestamp: float) -> DeviceActionResult:
        current = self._get_state(ctn)
        current_profile = self._get_profile(ctn)

        if current != DeviceState.NORMAL:
            logger.warning("degrade called on non-NORMAL device %s (state: %s)", ctn, current)
            return DeviceActionResult(
                success=False, router_ctn=ctn,
                previous_state=current, new_state=current,
                previous_profile=current_profile, new_profile=current_profile,
                action=None, timestamp=timestamp,
                message=f"Cannot degrade from {current}",
            )

        self._states[ctn] = DeviceState.DEGRADED
        self._profiles[ctn] = QualityProfile.DEGRADED
        self._update_history(ctn, DeviceState.DEGRADED, DeviceAction.DOWNGRADE, timestamp, QualityProfile.DEGRADED)

        logger.info("Device %s degraded to LOW at %.0f", ctn, timestamp)
        return DeviceActionResult(
            success=True, router_ctn=ctn,
            previous_state=DeviceState.NORMAL, new_state=DeviceState.DEGRADED,
            previous_profile=current_profile, new_profile=QualityProfile.DEGRADED,
            action=DeviceAction.DOWNGRADE, timestamp=timestamp,
        )

    def start_recovery(self, ctn: str, timestamp: float) -> DeviceActionResult:
        current = self._get_state(ctn)
        current_profile = self._get_profile(ctn)

        if current != DeviceState.DEGRADED:
            return DeviceActionResult(
                success=False, router_ctn=ctn,
                previous_state=current, new_state=current,
                previous_profile=current_profile, new_profile=current_profile,
                action=None, timestamp=timestamp,
                message=f"Cannot start recovery from {current}",
            )

        self._states[ctn] = DeviceState.RECOVERY_PENDING
        h = self._get_or_create_history(ctn)
        h.current_state = DeviceState.RECOVERY_PENDING
        h.cooldown_start_time = timestamp

        logger.info("Device %s recovery started at %.0f", ctn, timestamp)
        return DeviceActionResult(
            success=True, router_ctn=ctn,
            previous_state=DeviceState.DEGRADED, new_state=DeviceState.RECOVERY_PENDING,
            previous_profile=current_profile, new_profile=current_profile,
            action=None, timestamp=timestamp,
        )

    def step_up(self, ctn: str, timestamp: float) -> DeviceActionResult:
        current = self._get_state(ctn)
        current_profile = self._get_profile(ctn)

        if current != DeviceState.RECOVERY_PENDING:
            return DeviceActionResult(
                success=False, router_ctn=ctn,
                previous_state=current, new_state=current,
                previous_profile=current_profile, new_profile=current_profile,
                action=None, timestamp=timestamp,
                message=f"Cannot step up from {current}",
            )

        next_profile = _PROFILE_STEP_UP.get(current_profile)
        if next_profile is None:
            # Already HIGH — fully restored: remove from active states
            self._states.pop(ctn, None)
            self._profiles.pop(ctn, None)
            self._update_history(ctn, DeviceState.NORMAL, DeviceAction.RESTORE, timestamp, current_profile)
            return DeviceActionResult(
                success=True, router_ctn=ctn,
                previous_state=DeviceState.RECOVERY_PENDING, new_state=DeviceState.NORMAL,
                previous_profile=current_profile, new_profile=current_profile,
                action=DeviceAction.RESTORE, timestamp=timestamp,
            )

        self._profiles[ctn] = next_profile
        action = DeviceAction.RESTORE if next_profile == QualityProfile.NORMAL else DeviceAction.STEP_UP

        if next_profile == QualityProfile.NORMAL:
            # Fully restored
            # Fully restored: remove from active states
            self._states.pop(ctn, None)
            self._profiles.pop(ctn, None)
            self._update_history(ctn, DeviceState.NORMAL, DeviceAction.RESTORE, timestamp, next_profile)
        else:
            # Reset cooldown for next step
            h = self._get_or_create_history(ctn)
            h.current_profile = next_profile
            h.last_action = DeviceAction.STEP_UP
            h.last_action_time = timestamp
            h.cooldown_start_time = timestamp

        logger.info("Device %s stepped up to %s at %.0f", ctn, next_profile, timestamp)
        return DeviceActionResult(
            success=True, router_ctn=ctn,
            previous_state=DeviceState.RECOVERY_PENDING,
            new_state=self._get_state(ctn),
            previous_profile=current_profile, new_profile=next_profile,
            action=action, timestamp=timestamp,
        )

    def mark_unmanaged(self, ctn: str, timestamp: float) -> DeviceActionResult:
        """매핑 없는 단말을 UNMANAGED 상태로 전환한다."""
        current = self._get_state(ctn)
        current_profile = self._get_profile(ctn)
        if current == DeviceState.UNMANAGED:
            return DeviceActionResult(
                success=False, router_ctn=ctn,
                previous_state=current, new_state=current,
                previous_profile=current_profile, new_profile=current_profile,
                action=None, timestamp=timestamp,
                message="Already UNMANAGED",
            )
        self._states[ctn] = DeviceState.UNMANAGED
        self._update_history(ctn, DeviceState.UNMANAGED, DeviceAction.UNMANAGED, timestamp, current_profile)
        logger.info("Device %s marked UNMANAGED at %.0f", ctn, timestamp)
        return DeviceActionResult(
            success=True, router_ctn=ctn,
            previous_state=current, new_state=DeviceState.UNMANAGED,
            previous_profile=current_profile, new_profile=current_profile,
            action=DeviceAction.UNMANAGED, timestamp=timestamp,
        )

    def clear_unmanaged(self, ctn: str, timestamp: float) -> DeviceActionResult:
        """셀 복구 시 UNMANAGED 단말을 즉시 NORMAL로 전환한다 (쿨다운 없음)."""
        current = self._get_state(ctn)
        current_profile = self._get_profile(ctn)
        if current != DeviceState.UNMANAGED:
            return DeviceActionResult(
                success=False, router_ctn=ctn,
                previous_state=current, new_state=current,
                previous_profile=current_profile, new_profile=current_profile,
                action=None, timestamp=timestamp,
                message=f"Cannot clear_unmanaged from {current}",
            )
        self._states.pop(ctn, None)
        self._profiles.pop(ctn, None)
        self._update_history(ctn, DeviceState.NORMAL, DeviceAction.RESTORE, timestamp, QualityProfile.NORMAL)
        logger.info("Device %s cleared UNMANAGED -> NORMAL at %.0f", ctn, timestamp)
        return DeviceActionResult(
            success=True, router_ctn=ctn,
            previous_state=DeviceState.UNMANAGED, new_state=DeviceState.NORMAL,
            previous_profile=current_profile, new_profile=QualityProfile.NORMAL,
            action=DeviceAction.RESTORE, timestamp=timestamp,
        )

    def cancel_recovery(self, ctn: str, timestamp: float) -> DeviceActionResult:
        current = self._get_state(ctn)
        current_profile = self._get_profile(ctn)

        if current != DeviceState.RECOVERY_PENDING:
            return DeviceActionResult(
                success=False, router_ctn=ctn,
                previous_state=current, new_state=current,
                previous_profile=current_profile, new_profile=current_profile,
                action=None, timestamp=timestamp,
                message=f"Cannot cancel recovery from {current}",
            )

        self._states[ctn] = DeviceState.DEGRADED
        self._profiles[ctn] = QualityProfile.DEGRADED
        h = self._get_or_create_history(ctn)
        h.current_state = DeviceState.DEGRADED
        h.current_profile = QualityProfile.DEGRADED
        h.cooldown_start_time = None

        logger.info("Device %s recovery cancelled, back to DEGRADED at %.0f", ctn, timestamp)
        return DeviceActionResult(
            success=True, router_ctn=ctn,
            previous_state=DeviceState.RECOVERY_PENDING, new_state=DeviceState.DEGRADED,
            previous_profile=current_profile, new_profile=QualityProfile.DEGRADED,
            action=DeviceAction.DOWNGRADE, timestamp=timestamp,
        )

    def is_cooldown_expired(self, ctn: str, now: float) -> bool:
        h = self._histories.get(ctn)
        if h is None or h.cooldown_start_time is None:
            return False
        return (now - h.cooldown_start_time) >= self._recovery_cooldown_seconds

    def get_history(self, ctn: str) -> Optional[DeviceHistory]:
        return self._histories.get(ctn)

    def _get_or_create_history(self, ctn: str) -> DeviceHistory:
        if ctn not in self._histories:
            self._histories[ctn] = DeviceHistory(
                router_ctn=ctn,
                current_state=self._get_state(ctn),
                last_action=None,
                last_action_time=None,
                cooldown_start_time=None,
                current_profile=self._get_profile(ctn),
            )
        return self._histories[ctn]

    def _update_history(self, ctn: str, state: DeviceState, action: DeviceAction, timestamp: float, profile: QualityProfile) -> None:
        h = self._get_or_create_history(ctn)
        h.current_state = state
        h.last_action = action
        h.last_action_time = timestamp
        h.current_profile = profile
        if state != DeviceState.RECOVERY_PENDING:
            h.cooldown_start_time = None
