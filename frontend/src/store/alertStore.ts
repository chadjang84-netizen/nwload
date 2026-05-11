import { create } from 'zustand'
import type { AlertItem, AlertEventType } from '@/types'

const MAX_ALERTS = 100

interface AlertStore {
  alerts: AlertItem[]
  filter: AlertEventType | 'ALL'
  addAlert: (alert: AlertItem) => void
  setFilter: (f: AlertEventType | 'ALL') => void
  clearAll: () => void
}

export const useAlertStore = create<AlertStore>((set) => ({
  alerts: [],
  filter: 'ALL',
  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, MAX_ALERTS),
    })),
  setFilter: (filter) => set({ filter }),
  clearAll: () => set({ alerts: [] }),
}))
