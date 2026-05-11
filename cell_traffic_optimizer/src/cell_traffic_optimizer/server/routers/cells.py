from __future__ import annotations
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from ..deps import get_state
from ..state import AppState
from ..schemas import CellStatusSchema, CellDeviceDetailSchema, GroupingKeySchema
from ...models import GroupingKey

router = APIRouter(prefix="/api/cells", tags=["cells"])


def _ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _cell_to_schema(key, sm, aggregator, window_seconds: int) -> CellStatusSchema:
    state = sm.get_state(key)
    record = sm.get_stability_record(key)
    ctn_list = list(sm._ctn_map.get(key, set()))
    ul_rb_sum = sm.get_ul_rb(key)
    entered_at = record.state_entered_at if record else time.time()

    last_eval = aggregator._last_evaluated.get(key)
    next_eval_at = _ts(last_eval + window_seconds) if last_eval is not None else None

    return CellStatusSchema(
        groupingKey=GroupingKeySchema(ecgi=key.ecgi, band=key.band),
        state=state.value,
        ulRbSum=ul_rb_sum,
        ctnList=ctn_list,
        stateEnteredAt=_ts(entered_at),
        nextEvalAt=next_eval_at,
    )


@router.get("", response_model=list[CellStatusSchema])
def list_cells(state: AppState = Depends(get_state)):
    sm = state.pipeline._cell_sm
    agg = state.pipeline._aggregator
    window_seconds = state.pipeline._aggregator._window_seconds
    return [_cell_to_schema(key, sm, agg, window_seconds) for key in sm._states]


@router.get("/{ecgi}/{band}/devices", response_model=list[CellDeviceDetailSchema])
def list_cell_devices(ecgi: int, band: int, state: AppState = Depends(get_state)):
    key = GroupingKey(ecgi=ecgi, band=band)
    sm = state.pipeline._cell_sm
    if key not in sm._states:
        raise HTTPException(status_code=404, detail="Cell not found")

    device_sm = state.pipeline._device_sm
    aggregator = state.pipeline._aggregator

    # 해당 셀의 최신 이벤트를 CTN별로 집계
    latest: dict[str, object] = {}
    for event in aggregator._events:
        if event.grouping_key == key:
            prev = latest.get(event.router_ctn)
            if prev is None or event.timestamp > prev.timestamp:
                latest[event.router_ctn] = event

    result = []
    for ctn, event in latest.items():
        d_state = device_sm._get_state(ctn)
        d_profile = device_sm._profiles.get(ctn)
        result.append(CellDeviceDetailSchema(
            routerCtn=ctn,
            band=event.grouping_key.band,
            ecgi=event.grouping_key.ecgi,
            ulRbUsage=event.ul_rb_usage,
            timestamp=_ts(event.timestamp),
            deviceState=d_state.value if d_state else "NORMAL",
            qualityProfile=d_profile.value if d_profile else "NORMAL",
        ))

    result.sort(key=lambda x: x.ulRbUsage, reverse=True)
    return result
