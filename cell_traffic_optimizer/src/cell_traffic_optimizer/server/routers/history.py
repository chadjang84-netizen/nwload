from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from ..deps import get_state
from ..state import AppState
from ..schemas import DeviceHistoryItemSchema, CellHistoryItemSchema

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/devices", response_model=list[DeviceHistoryItemSchema])
def get_device_history(
    ctn: Optional[str] = Query(None),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    state: AppState = Depends(get_state),
):
    rows = state.event_store.query_device_history(
        ctn=ctn or None,
        from_ts=from_ or None,
        to_ts=to or None,
    )
    result = []
    for r in rows:
        try:
            result.append(DeviceHistoryItemSchema(**r))
        except Exception:
            pass
    return result


@router.get("/cells", response_model=list[CellHistoryItemSchema])
def get_cell_history(
    ecgi: Optional[int] = Query(None),
    band: Optional[int] = Query(None),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    state: AppState = Depends(get_state),
):
    rows = state.event_store.query_cell_history(
        ecgi=ecgi,
        band=band,
        from_ts=from_ or None,
        to_ts=to or None,
    )
    result = []
    for r in rows:
        try:
            result.append(CellHistoryItemSchema(
                id=r["id"],
                timestamp=r["timestamp"],
                eventType=r["eventType"],
                ecgi=r["groupingKey"]["ecgi"],
                band=r["groupingKey"]["band"],
                message=r["message"],
            ))
        except Exception:
            pass
    return result


@router.delete("/reset")
def reset_history(state: AppState = Depends(get_state)):
    deleted = state.event_store.reset()
    size = state.event_store.size()
    return {"deleted": deleted, "rows": size["rows"], "bytes": size["bytes"]}


@router.get("/stats")
def history_stats(state: AppState = Depends(get_state)):
    return state.event_store.size()
