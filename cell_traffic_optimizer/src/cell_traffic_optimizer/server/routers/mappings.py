from __future__ import annotations
import time
from fastapi import APIRouter, Depends, HTTPException
from ..deps import get_state
from ..state import AppState
from ..schemas import MappingEntrySchema, CreateMappingRequest

router = APIRouter(prefix="/api/mappings", tags=["mappings"])

@router.get("", response_model=list[MappingEntrySchema])
def list_mappings(state: AppState = Depends(get_state)):
    return [
        MappingEntrySchema(routerCtn=e.router_ctn, cameraIds=list(e.camera_ids))
        for e in state.device_mapping.all()
    ]

@router.post("", response_model=MappingEntrySchema, status_code=201)
def create_mapping(body: CreateMappingRequest, state: AppState = Depends(get_state)):
    if state.camera_registry.get(body.cameraId) is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    state.device_mapping.add_mapping(body.routerCtn, body.cameraId, time.time())
    entry = state.device_mapping.get_entry(body.routerCtn)
    return MappingEntrySchema(routerCtn=entry.router_ctn, cameraIds=list(entry.camera_ids))

@router.put("/{router_ctn}", response_model=MappingEntrySchema)
def update_mapping(router_ctn: str, body: CreateMappingRequest, state: AppState = Depends(get_state)):
    """기존 CTN의 카메라 ID를 새 값으로 교체."""
    if state.camera_registry.get(body.cameraId) is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    entry = state.device_mapping.get_entry(router_ctn)
    if entry is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    now = time.time()
    for cam_id in list(entry.camera_ids):
        state.device_mapping.remove_mapping(router_ctn, cam_id, now)
    state.device_mapping.add_mapping(router_ctn, body.cameraId, now)
    entry = state.device_mapping.get_entry(router_ctn)
    return MappingEntrySchema(routerCtn=entry.router_ctn, cameraIds=list(entry.camera_ids))


@router.delete("/{router_ctn}", status_code=204)
def delete_mapping(router_ctn: str, state: AppState = Depends(get_state)):
    entry = state.device_mapping.get_entry(router_ctn)
    if entry is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    for cam_id in list(entry.camera_ids):
        state.device_mapping.remove_mapping(router_ctn, cam_id, time.time())
