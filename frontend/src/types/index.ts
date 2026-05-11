// ── 열거형 ───────────────────────────────────────────────────────────────────
export type CellState = 'NORMAL' | 'WARNING' | 'CONGESTION' | 'OVERLOAD'
export type DeviceState = 'NORMAL' | 'DEGRADED' | 'RECOVERY_PENDING' | 'UNMANAGED'
export type QualityProfile = 'DEGRADED' | 'STEP_UP' | 'NORMAL'
export type DeviceAction = 'DOWNGRADE' | 'STEP_UP' | 'RESTORE'
export type AlertEventType =
  | 'CELL_OVERLOAD'
  | 'CELL_RECOVERY'
  | 'DEVICE_DEGRADED'
  | 'DEVICE_RESTORED'
  | 'DEVICE_UNMANAGED'

// ── 핵심 모델 ─────────────────────────────────────────────────────────────────
export interface GroupingKey {
  ecgi: number
  band: number
}

export interface CellStatus {
  groupingKey: GroupingKey
  state: CellState
  ulRbSum: number
  ctnList: string[]
  stateEnteredAt: string
  nextEvalAt: string | null
}

export interface CellDeviceDetail {
  routerCtn: string
  band: number
  ecgi: number
  ulRbUsage: number
  timestamp: string
  deviceState: DeviceState
  qualityProfile: QualityProfile
}

export interface DeviceStatus {
  routerCtn: string
  state: DeviceState
  currentProfile: QualityProfile
  cooldownStartTime: string | null
  cooldownRemainingSeconds: number | null
  lastAction: DeviceAction | null
  lastActionTime: string | null
}

// ── 알림 ──────────────────────────────────────────────────────────────────────
export interface AlertItem {
  id: string
  timestamp: string
  eventType: AlertEventType
  groupingKey?: GroupingKey
  routerCtn?: string
  message: string
}

// ── WebSocket 이벤트 ──────────────────────────────────────────────────────────
export type WSEvent =
  | { type: 'cell_state_changed'; data: CellStatus }
  | { type: 'device_state_changed'; data: DeviceStatus }
  | { type: 'alert'; data: AlertItem }

// ── 설정 ──────────────────────────────────────────────────────────────────────
export interface ThresholdConfig {
  warning: number
  congestion: number
  overloadEnter: number
  overloadExit: number
}

export interface DegradationConfig {
  degradedRatio: number
  stepUpRatio: number
}

export interface BandThreshold extends ThresholdConfig {
  band: number
}

export interface Configuration {
  thresholds: BandThreshold[]
  degradation: DegradationConfig
  slidingWindowSeconds: number
  recoveryCooldownSeconds: number
  stepUpIntervalSeconds: number
  maxOnvifRetries: number
}

// ── 카메라/매핑 ───────────────────────────────────────────────────────────────
export interface CameraEntry {
  cameraId: string
  ipAddress: string
  onvifPort: number
  username: string
  profileToken: string
  isReachable: boolean
}

export interface MappingEntry {
  routerCtn: string
  cameraIds: string[]
}

// ── ONVIF 커맨드 이력 ────────────────────────────────────────────────────────

export interface CameraCommandLog {
  timestamp: string
  cameraId: string | null
  routerCtn: string
  command: string
  profile: string
  bitrate: number
  framerate: number
  resolution: [number, number]
  success: boolean
  error: string
}

// ── 이력 ──────────────────────────────────────────────────────────────────────
export interface DeviceHistoryItem {
  routerCtn: string
  previousState: DeviceState
  newState: DeviceState
  action: DeviceAction | null
  timestamp: string
  profile: QualityProfile
}

export interface CellHistoryItem {
  id: string
  timestamp: string
  eventType: 'CELL_OVERLOAD' | 'CELL_RECOVERY'
  ecgi: number
  band: number
  message: string
}

export interface CellStabilityItem {
  ecgi: number
  band: number
  currentState: CellState
  stateEnteredAt: string
  normalDurationSeconds: number
}
