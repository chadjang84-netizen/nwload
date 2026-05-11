from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends
from ..deps import get_state
from ..state import AppState
from ..schemas import DeviceStatusSchema

router = APIRouter(prefix="/api/devices", tags=["devices"])


def _device_to_schema(ctn: str, sm) -> DeviceStatusSchema:
    state = sm._get_state(ctn)
    profile = sm._get_profile(ctn)
    history = sm.get_history(ctn)

    cooldown_start: Optional[float] = None
    cooldown_remaining: Optional[float] = None
    last_action = None
    last_action_time = None

    if history:
        if history.cooldown_start_time is not None:
            cooldown_start = history.cooldown_start_time
            elapsed = time.time() - cooldown_start
            cooldown_remaining = max(0.0, sm._recovery_cooldown_seconds - elapsed)
        if history.last_action:
            last_action = history.last_action.value
        if history.last_action_time is not None:
            last_action_time = datetime.fromtimestamp(history.last_action_time, tz=timezone.utc).isoformat()

    return DeviceStatusSchema(
        routerCtn=ctn,
        state=state.value,
        currentProfile=profile.value,
        cooldownStartTime=datetime.fromtimestamp(cooldown_start, tz=timezone.utc).isoformat() if cooldown_start else None,
        cooldownRemainingSeconds=cooldown_remaining,
        lastAction=last_action,
        lastActionTime=last_action_time,
    )

@router.get("", response_model=list[DeviceStatusSchema])
def list_devices(state: AppState = Depends(get_state)):
    sm = state.pipeline._device_sm
    return [_device_to_schema(ctn, sm) for ctn in sm._states]
