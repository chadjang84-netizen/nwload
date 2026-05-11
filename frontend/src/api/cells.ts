import api from './client'
import type { CellStatus, CellDeviceDetail } from '@/types'

export const fetchCells = () =>
  api.get<CellStatus[]>('/cells').then((r) => r.data)

export const fetchCellDevices = (ecgi: number, band: number) =>
  api.get<CellDeviceDetail[]>(`/cells/${ecgi}/${band}/devices`).then((r) => r.data)
