import api from './client'
import type { Configuration } from '@/types'

export const fetchConfig = () =>
  api.get<Configuration>('/config').then((r) => r.data)

export const saveConfig = (config: Configuration) =>
  api.post<Configuration>('/config', config).then((r) => r.data)
