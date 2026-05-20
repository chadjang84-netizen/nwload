from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from ..deps import get_state
from ..state import AppState
from ..schemas import CameraEntrySchema, CreateCameraRequest, UpdateCameraRequest, CameraCommandLogSchema

router = APIRouter(prefix="/api/cameras", tags=["cameras"])

_ALLOWED_CODECS = {"H264", "H265"}


def _normalize_codec(value: str) -> str:
    norm = (value or "H264").upper().replace(".", "")
    if norm not in _ALLOWED_CODECS:
        raise HTTPException(status_code=422, detail=f"Unsupported videoCodec: {value} (allowed: H264, H265)")
    return norm


def _normalize_media_path(value: str) -> str:
    if not value:
        raise HTTPException(status_code=422, detail="mediaServicePath must not be empty")
    trimmed = value.strip().rstrip("/")
    if not trimmed.startswith("/"):
        raise HTTPException(status_code=422, detail="mediaServicePath must start with '/'")
    return trimmed or "/"


def _to_schema(entry) -> CameraEntrySchema:
    return CameraEntrySchema(
        cameraId=entry.camera_id,
        ipAddress=entry.ip_address,
        onvifPort=entry.onvif_port,
        username=entry.username,
        profileToken=entry.profile_token,
        isReachable=entry.is_reachable,
        useTls=getattr(entry, "use_tls", False),
        mediaServicePath=getattr(entry, "media_service_path", "/onvif/media"),
        videoCodec=getattr(entry, "video_codec", "H264"),
    )


@router.get("", response_model=list[CameraEntrySchema])
def list_cameras(state: AppState = Depends(get_state)):
    return [_to_schema(e) for e in state.camera_registry.all()]


@router.post("", response_model=CameraEntrySchema, status_code=201)
def create_camera(body: CreateCameraRequest, state: AppState = Depends(get_state)):
    if state.camera_registry.get(body.cameraId):
        raise HTTPException(status_code=409, detail="Camera ID already exists")
    codec = _normalize_codec(body.videoCodec)
    path = _normalize_media_path(body.mediaServicePath)
    entry = state.camera_registry.register(
        camera_id=body.cameraId,
        ip_address=body.ipAddress,
        onvif_port=body.onvifPort,
        username=body.username,
        password=body.password,
        profile_token=body.profileToken,
        use_tls=body.useTls,
        media_service_path=path,
        video_codec=codec,
    )
    return _to_schema(entry)


@router.put("/{camera_id}", response_model=CameraEntrySchema)
def update_camera(camera_id: str, body: UpdateCameraRequest, state: AppState = Depends(get_state)):
    codec = _normalize_codec(body.videoCodec) if body.videoCodec is not None else None
    path = _normalize_media_path(body.mediaServicePath) if body.mediaServicePath is not None else None
    entry = state.camera_registry.update(
        camera_id=camera_id,
        ip_address=body.ipAddress,
        onvif_port=body.onvifPort,
        username=body.username,
        password=body.password,
        profile_token=body.profileToken,
        use_tls=body.useTls,
        media_service_path=path,
        video_codec=codec,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return _to_schema(entry)


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
