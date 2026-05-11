import { create } from 'zustand'
import type { DeviceStatus } from '@/types'

interface DeviceStore {
  devices: Map<string, DeviceStatus>
  setStatus: (status: DeviceStatus) => void
  setAll: (list: DeviceStatus[]) => void
}

export const useDeviceStore = create<DeviceStore>((set) => ({
  devices: new Map(),
  setStatus: (status) =>
    set((state) => {
      const next = new Map(state.devices)
      if (status.state === 'NORMAL') {
        // 완전 복구된 단말은 제거
        next.delete(status.routerCtn)
      } else {
        next.set(status.routerCtn, status)
      }
      return { devices: next }
    }),
  setAll: (list) =>
    set((state) => {
      // REST 응답 기준으로 교체하되, DEGRADED/RECOVERY_PENDING 단말은 항상 유지
      const next = new Map<string, DeviceStatus>()
      // 기존 비정상 단말을 먼저 보존
      state.devices.forEach((d, key) => {
        if (d.state !== 'NORMAL') next.set(key, d)
      })
      // REST 응답으로 덮어쓰기 (서버가 권위)
      list.forEach((d) => {
        if (d.state !== 'NORMAL') {
          next.set(d.routerCtn, d)
        } else {
          next.delete(d.routerCtn)
        }
      })
      return { devices: next }
    }),
}))
