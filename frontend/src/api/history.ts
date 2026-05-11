import api from './client'
import type { DeviceHistoryItem, CellHistoryItem, CellStabilityItem } from '@/types'

export interface DeviceHistoryParams {
  ctn?: string
  from?: string
  to?: string
}

export interface CellHistoryParams {
  ecgi?: number
  band?: number
  from?: string
  to?: string
}

export const fetchDeviceHistory = (params: DeviceHistoryParams) =>
  api.get<DeviceHistoryItem[]>('/history/devices', { params }).then((r) => r.data)

export const fetchCellHistory = (params: CellHistoryParams) =>
  api.get<CellHistoryItem[]>('/history/cells', { params }).then((r) => r.data)

export const fetchCellStability = () =>
  api.get<CellStabilityItem[]>('/history/cells').then((r) => r.data)

export const resetHistory = () =>
  api.delete<{ deleted: number; rows: number; bytes: number }>('/history/reset').then((r) => r.data)

export const fetchHistoryStats = () =>
  api.get<{ rows: number; bytes: number }>('/history/stats').then((r) => r.data)
