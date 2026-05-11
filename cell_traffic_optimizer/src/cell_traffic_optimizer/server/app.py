from __future__ import annotations
import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .state import create_app_state
from .routers import config, cells, devices, history, cameras, mappings, ws, ingest
from .broadcast import broadcast
from ..models import CellState, DeviceState

logger = logging.getLogger(__name__)

UDP_HOST = "0.0.0.0"
UDP_PORT = 9000


class _UDPProtocol(asyncio.DatagramProtocol):
    """asyncio UDP 수신기 — 패킷을 파이프라인에 직접 전달한다."""

    def __init__(self, app_state):
        self._state = app_state
        self._loop: asyncio.AbstractEventLoop | None = None

    def connection_made(self, transport) -> None:
        self._loop = asyncio.get_running_loop()

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        self._loop.create_task(self._process(data, addr))

    async def _process(self, data: bytes, addr: tuple) -> None:
        now = time.time()
        result = self._state.pipeline.process_packet(data, now)
        if not result.success:
            logger.warning("UDP packet rejected from %s:%d — %s", addr[0], addr[1], result.errors)
            return
        logger.debug("UDP PKT from %s:%d  ctn=%-15s events=%d cells=%d",
                     addr[0], addr[1], result.router_ctn, result.events_generated, len(result.affected_keys))
        await ingest._handle_ingest_result(self._state, result, now)

    def error_received(self, exc: Exception) -> None:
        logger.error("UDP error: %s", exc)


async def _broadcast_window_result(state, pipeline_result, now: float) -> None:
    """check_window_expiry 결과를 WebSocket 브로드캐스트 및 이벤트 로그에 기록한다."""
    from .routers.ingest import _make_alert
    sm = state.pipeline._cell_sm
    dsm = state.pipeline._device_sm
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    for tr in pipeline_result.cell_transitions:
        key = tr.grouping_key
        ul_rb_sum = sm.get_ul_rb(key)
        ctn_list = list(sm._ctn_map.get(key, set()))
        record = sm.get_stability_record(key)
        entered_at = datetime.fromtimestamp(
            record.state_entered_at if record else now, tz=timezone.utc
        ).isoformat()
        await broadcast(state, {
            "type": "cell_state_changed",
            "data": {
                "groupingKey": {"ecgi": key.ecgi, "band": key.band},
                "state": sm.get_state(key).value,
                "ulRbSum": ul_rb_sum,
                "ctnList": ctn_list,
                "stateEnteredAt": entered_at,
            },
        })
        if tr.new_state == CellState.OVERLOAD:
            alert = _make_alert("CELL_OVERLOAD", f"Cell ECGI:{key.ecgi} Band:{key.band} overloaded (UL_RB={ul_rb_sum})", key)
            state.event_store.insert(alert)
            await broadcast(state, {"type": "alert", "data": alert})
        elif tr.new_state == CellState.NORMAL:
            alert = _make_alert("CELL_RECOVERY", f"Cell ECGI:{key.ecgi} Band:{key.band} recovered", key)
            state.event_store.insert(alert)
            await broadcast(state, {"type": "alert", "data": alert})

    for da in pipeline_result.device_actions:
        if not da.success:
            continue
        hist = dsm.get_history(da.router_ctn)
        cooldown_remaining = None
        if hist and hist.cooldown_start_time:
            elapsed_cd = now - hist.cooldown_start_time
            cooldown_remaining = max(0.0, dsm._recovery_cooldown_seconds - elapsed_cd)
        await broadcast(state, {
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
        await broadcast(state, {"type": "alert", "data": alert})


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 자체 로거는 DEBUG, uvicorn access 로거는 WARNING으로 잡음 줄이기
    logging.getLogger("cell_traffic_optimizer").setLevel(logging.DEBUG)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    state = create_app_state()
    app.state.app = state

    async def recovery_loop():
        while True:
            await asyncio.sleep(5)
            try:
                now = time.time()

                # 슬라이딩 윈도우 만료 판정 — ul_rb_sum 기반 셀 상태 전이
                window_result = state.pipeline.check_window_expiry(now)
                await _broadcast_window_result(state, window_result, now)

                actions = state.pipeline.check_recovery_timers(now)
                if not actions:
                    continue

                now_iso = datetime.now(tz=timezone.utc).isoformat()
                dsm = state.pipeline._device_sm
                for action in actions:
                    if not action.success:
                        continue

                    hist = dsm.get_history(action.router_ctn)
                    cooldown_remaining = None
                    if hist and hist.cooldown_start_time:
                        elapsed = now - hist.cooldown_start_time
                        cooldown_remaining = max(0.0, dsm._recovery_cooldown_seconds - elapsed)

                    await broadcast(state, {
                        "type": "device_state_changed",
                        "data": {
                            "routerCtn": action.router_ctn,
                            "state": action.new_state.value,
                            "currentProfile": action.new_profile.value,
                            "cooldownStartTime": None,
                            "cooldownRemainingSeconds": cooldown_remaining,
                            "lastAction": action.action.value if action.action else None,
                            "lastActionTime": now_iso,
                        },
                    })

                    event_type = "DEVICE_RESTORED"
                    alert = {
                        "id": str(uuid.uuid4()),
                        "timestamp": now_iso,
                        "eventType": event_type,
                        "groupingKey": None,
                        "routerCtn": action.router_ctn,
                        "message": f"Device {action.router_ctn} step-up to {action.new_profile.value}",
                    }
                    state.event_store.insert(alert)
                    await broadcast(state, {"type": "alert", "data": alert})

            except Exception as e:
                logger.error("Recovery timer error: %s", e)

    # UDP 서버 시작
    loop = asyncio.get_event_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: _UDPProtocol(state),
        local_addr=(UDP_HOST, UDP_PORT),
    )
    logger.info("UDP listener started on %s:%d", UDP_HOST, UDP_PORT)

    task = asyncio.create_task(recovery_loop())
    logger.info("Cell Traffic Optimizer API started (HTTP :8000, UDP :%d)", UDP_PORT)
    yield
    task.cancel()
    transport.close()
    logger.info("UDP listener stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="Cell Traffic Optimizer", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(config.router)
    app.include_router(cells.router)
    app.include_router(devices.router)
    app.include_router(history.router)
    app.include_router(cameras.router)
    app.include_router(mappings.router)
    app.include_router(ws.router)
    app.include_router(ingest.router)

    return app


app = create_app()
