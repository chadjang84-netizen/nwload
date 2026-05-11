from __future__ import annotations
import time
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from ..deps import get_state
from ..state import AppState
from ..broadcast import broadcast
from ...models import CellState, DeviceState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["ingest"])

_pkt_count = 0  # 수신 패킷 카운터 (프로세스 생애)


def _make_alert(event_type: str, message: str, grouping_key=None, router_ctn: str = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "eventType": event_type,
        "groupingKey": {"ecgi": grouping_key.ecgi, "band": grouping_key.band} if grouping_key else None,
        "routerCtn": router_ctn,
        "message": message,
    }


async def _handle_ingest_result(state: AppState, result, now: float) -> dict:
    """파이프라인 처리 결과를 브로드캐스트하고 이벤트를 저장한다.
    HTTP 엔드포인트와 UDP 수신기가 공통으로 사용한다."""
    broadcasts = []
    sm = state.pipeline._cell_sm
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    # 영향받은 모든 셀의 최신 UL_RB 브로드캐스트
    for key in result.affected_keys:
        ul_rb_sum = sm.get_ul_rb(key)
        ctn_list = list(sm._ctn_map.get(key, set()))
        record = sm.get_stability_record(key)
        entered_at = datetime.fromtimestamp(
            record.state_entered_at if record else now, tz=timezone.utc
        ).isoformat()
        broadcasts.append({
            "type": "cell_state_changed",
            "data": {
                "groupingKey": {"ecgi": key.ecgi, "band": key.band},
                "state": sm.get_state(key).value,
                "ulRbSum": ul_rb_sum,
                "ctnList": ctn_list,
                "stateEnteredAt": entered_at,
            },
        })

    # Cell state transitions -> alert
    for tr in result.cell_transitions:
        key = tr.grouping_key
        ul_rb_sum = sm.get_ul_rb(key)
        if tr.new_state == CellState.OVERLOAD:
            alert = _make_alert("CELL_OVERLOAD", f"Cell ECGI:{key.ecgi} Band:{key.band} overloaded (UL_RB={ul_rb_sum})", key)
            state.event_store.insert(alert)
            broadcasts.append({"type": "alert", "data": alert})
        elif tr.previous_state == CellState.OVERLOAD and tr.new_state == CellState.NORMAL:
            alert = _make_alert("CELL_RECOVERY", f"Cell ECGI:{key.ecgi} Band:{key.band} recovered", key)
            state.event_store.insert(alert)
            broadcasts.append({"type": "alert", "data": alert})

    # Device state changes -> broadcast + alert
    for da in result.device_actions:
        if not da.success:
            continue
        dsm = state.pipeline._device_sm
        hist = dsm.get_history(da.router_ctn)
        cooldown_remaining = None
        if hist and hist.cooldown_start_time:
            elapsed_cd = now - hist.cooldown_start_time
            cooldown_remaining = max(0.0, dsm._recovery_cooldown_seconds - elapsed_cd)

        broadcasts.append({
            "type": "device_state_changed",
            "data": {
                "routerCtn": da.router_ctn,
                "state": da.new_state.value,
                "currentProfile": da.new_profile.value,
                "cooldownStartTime": None,
                "cooldownRemainingSeconds": cooldown_remaining,
                "lastAction": da.action.value if da.action else None,
                "lastActionTime": now_iso,
            },
        })

        if da.new_state == DeviceState.DEGRADED:
            alert = _make_alert("DEVICE_DEGRADED", f"Device {da.router_ctn} degraded to {da.new_profile.value}", router_ctn=da.router_ctn)
        elif da.new_state == DeviceState.UNMANAGED:
            alert = _make_alert("DEVICE_UNMANAGED", f"Device {da.router_ctn} — no camera mapping", router_ctn=da.router_ctn)
        else:
            alert = _make_alert("DEVICE_RESTORED", f"Device {da.router_ctn} restored to {da.new_profile.value}", router_ctn=da.router_ctn)
        state.event_store.insert(alert)
        broadcasts.append({"type": "alert", "data": alert})

    for msg in broadcasts:
        await broadcast(state, msg)

    return {
        "success": True,
        "routerCtn": result.router_ctn,
        "eventsGenerated": result.events_generated,
        "cellTransitions": len(result.cell_transitions),
        "deviceActions": len(result.device_actions),
    }


@router.post("/packet")
async def ingest_packet(request: Request, state: AppState = Depends(get_state)):
    global _pkt_count
    data = await request.body()
    now = time.time()

    result = state.pipeline.process_packet(data, now)

    if not result.success:
        logger.warning("HTTP packet rejected (%dB): %s", len(data), result.errors)
        return JSONResponse(status_code=400, content={"errors": result.errors})

    _pkt_count += 1
    logger.debug("HTTP PKT #%d  ctn=%-15s events=%d cells=%d",
                 _pkt_count, result.router_ctn, result.events_generated, len(result.affected_keys))
    if _pkt_count % 10 == 0:
        logger.info("HTTP PKT #%-5d ctn=%-15s events=%d cells=%d (total: %d)",
                    _pkt_count, result.router_ctn, result.events_generated,
                    len(result.affected_keys), _pkt_count)

    return await _handle_ingest_result(state, result, now)
