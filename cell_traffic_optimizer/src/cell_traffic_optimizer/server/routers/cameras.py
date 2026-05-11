from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from ..deps import get_state
from ..state import AppState
from ..schemas import CameraEntrySchema, CreateCameraRequest, UpdateCameraRequest, CameraCommandLogSchema

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=list[CameraEntrySchema])
def list_cameras(state: AppState = Depends(get_state)):
    return [
        CameraEntrySchema(
            cameraId=e.camera_id,
            ipAddress=e.ip_address,
            onvifPort=e.onvif_port,
            username=e.username,
            profileToken=e.profile_token,
            isReachable=e.is_reachable,
        )
        for e in state.camera_registry.all()
    ]


@router.post("", response_model=CameraEntrySchema, status_code=201)
def create_camera(body: CreateCameraRequest, state: AppState = Depends(get_state)):
    if state.camera_registry.get(body.cameraId):
        raise HTTPException(status_code=409, detail="Camera ID already exists")
    entry = state.camera_registry.register(
        camera_id=body.cameraId,
        ip_address=body.ipAddress,
        onvif_port=body.onvifPort,
        username=body.username,
        password=body.password,
        profile_token=body.profileToken,
    )
    return CameraEntrySchema(
        cameraId=entry.camera_id,
        ipAddress=entry.ip_address,
        onvifPort=entry.onvif_port,
        username=entry.username,
        profileToken=entry.profile_token,
        isReachable=entry.is_reachable,
    )


@router.put("/{camera_id}", response_model=CameraEntrySchema)
def update_camera(camera_id: str, body: UpdateCameraRequest, state: AppState = Depends(get_state)):
    entry = state.camera_registry.update(
        camera_id=camera_id,
        ip_address=body.ipAddress,
        onvif_port=body.onvifPort,
        username=body.username,
        password=body.password,
        profile_token=body.profileToken,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return CameraEntrySchema(
        cameraId=entry.camera_id,
        ipAddress=entry.ip_address,
        onvifPort=entry.onvif_port,
        username=entry.username,
        profileToken=entry.profile_token,
        isReachable=entry.is_reachable,
    )


@router.delete("/{camera_id}", status_code=204)
def delete_camera(camera_id: str, state: AppState = Depends(get_state)):
    if not state.camera_registry.remove(camera_id):
        raise HTTPException(status_code=404, detail="Camera not found")


@router.get("/command-log", response_model=list[CameraCommandLogSchema])
def get_command_log(state: AppState = Depends(get_state)):
    ctrl = state.pipeline._quality_ctrl
    return [
        CameraCommandLogSchema(
            timestamp=e.timestamp,
            cameraId=e.camera_id if e.camera_id else None,
            routerCtn=e.router_ctn,
            command=e.command,
            profile=e.profile,
            bitrate=e.bitrate,
            framerate=e.framerate,
            resolution=list(e.resolution),
            success=e.success,
            error=e.error,
        )
        for e in ctrl.command_log
    ]
