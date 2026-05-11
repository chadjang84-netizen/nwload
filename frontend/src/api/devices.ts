import api from './client'
import type { DeviceStatus } from '@/types'

export const fetchDevices = () =>
  api.get<DeviceStatus[]>('/devices').then((r) => r.data)
