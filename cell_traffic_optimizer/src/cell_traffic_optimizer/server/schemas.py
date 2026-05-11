from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


# ── 설정 ─────────────────────────────────────────────────────────────────────

class DegradationConfigSchema(BaseModel):
    degradedRatio: float
    stepUpRatio: float


class BandThresholdSchema(BaseModel):
    band: int
    warning: int
    congestion: int
    overloadEnter: int
    overloadExit: int


class ConfigurationSchema(BaseModel):
    thresholds: list[BandThresholdSchema]
    degradation: DegradationConfigSchema
    slidingWindowSeconds: int
    recoveryCooldownSeconds: int
    stepUpIntervalSeconds: int
    maxOnvifRetries: int


# ── 셀 상태 ──────────────────────────────────────────────────────────────────

class GroupingKeySchema(BaseModel):
    ecgi: int
    band: int


class CellStatusSchema(BaseModel):
    groupingKey: GroupingKeySchema
    state: str
    ulRbSum: int
    ctnList: list[str]
    stateEnteredAt: str
    nextEvalAt: Optional[str] = None


class CellDeviceDetailSchema(BaseModel):
    routerCtn: str
    band: int
    ecgi: int
    ulRbUsage: int
    timestamp: str
    deviceState: str
    qualityProfile: str


# ── 단말 상태 ─────────────────────────────────────────────────────────────────

class DeviceStatusSchema(BaseModel):
    routerCtn: str
    state: str
    currentProfile: str
    cooldownStartTime: Optional[str]
    cooldownRemainingSeconds: Optional[float]
    lastAction: Optional[str]
    lastActionTime: Optional[str]


# ── 알림 ──────────────────────────────────────────────────────────────────────

class AlertSchema(BaseModel):
    id: str
    timestamp: str
    eventType: str
    groupingKey: Optional[GroupingKeySchema] = None
    routerCtn: Optional[str] = None
    message: str


# ── 이력 ──────────────────────────────────────────────────────────────────────

class DeviceHistoryItemSchema(BaseModel):
    routerCtn: str
    previousState: str
    newState: str
    action: Optional[str]
    timestamp: str
    profile: str


class CellHistoryItemSchema(BaseModel):
    id: str
    timestamp: str
    eventType: str
    ecgi: int
    band: int
    message: str


# ── 카메라 ────────────────────────────────────────────────────────────────────

class CameraEntrySchema(BaseModel):
    cameraId: str
    ipAddress: str
    onvifPort: int
    username: str
    profileToken: str
    isReachable: bool


class CreateCameraRequest(BaseModel):
    cameraId: str
    ipAddress: str
    onvifPort: int
    username: str
    password: str
    profileToken: str


class UpdateCameraRequest(BaseModel):
    ipAddress: str
    onvifPort: int
    username: str
    password: Optional[str] = None   # None이면 기존 비밀번호 유지
    profileToken: str


# ── ONVIF 커맨드 이력 ────────────────────────────────────────────────────────

class CameraCommandLogSchema(BaseModel):
    timestamp: str
    cameraId: Optional[str]
    routerCtn: str
    command: str
    profile: str
    bitrate: int
    framerate: int
    resolution: list[int]
    success: bool
    error: str


# ── 매핑 ──────────────────────────────────────────────────────────────────────

class MappingEntrySchema(BaseModel):
    routerCtn: str
    cameraIds: list[str]


class CreateMappingRequest(BaseModel):
    routerCtn: str
    cameraId: str
