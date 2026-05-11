import api from './client'
import type { CameraEntry, MappingEntry, CameraCommandLog } from '@/types'

export const fetchCameras = () =>
  api.get<CameraEntry[]>('/cameras').then((r) => r.data)

export const createCamera = (data: Omit<CameraEntry, 'isReachable'> & { password: string }) =>
  api.post<CameraEntry>('/cameras', data).then((r) => r.data)

export const updateCamera = (cameraId: string, data: { ipAddress: string; onvifPort: number; username: string; password?: string; profileToken: string }) =>
  api.put<CameraEntry>(`/cameras/${cameraId}`, data).then((r) => r.data)

export const deleteCamera = (cameraId: string) =>
  api.delete(`/cameras/${cameraId}`)

export const fetchMappings = () =>
  api.get<MappingEntry[]>('/mappings').then((r) => r.data)

export const createMapping = (routerCtn: string, cameraId: string) =>
  api.post<MappingEntry>('/mappings', { routerCtn, cameraId }).then((r) => r.data)

export const updateMapping = (routerCtn: string, cameraId: string) =>
  api.put<MappingEntry>(`/mappings/${routerCtn}`, { routerCtn, cameraId }).then((r) => r.data)

export const deleteMapping = (routerCtn: string) =>
  api.delete(`/mappings/${routerCtn}`)

export const fetchCommandLog = () =>
  api.get<CameraCommandLog[]>('/cameras/command-log').then((r) => r.data)
