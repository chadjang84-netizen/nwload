import { create } from 'zustand'
import type { CellStatus } from '@/types'

interface CellStore {
  cells: Map<string, CellStatus>
  setStatus: (status: CellStatus) => void
  setAll: (list: CellStatus[]) => void
}

const keyOf = (s: CellStatus) => `${s.groupingKey.ecgi}:${s.groupingKey.band}`

export const useCellStore = create<CellStore>((set) => ({
  cells: new Map(),
  setStatus: (status) =>
    set((state) => {
      const next = new Map(state.cells)
      next.set(keyOf(status), status)
      return { cells: next }
    }),
  setAll: (list) =>
    set(() => {
      // REST 응답이 권위: 서버에 없는 셀(윈도우 만료)은 제거, 있는 셀은 갱신
      const next = new Map<string, CellStatus>()
      list.forEach((s) => next.set(keyOf(s), s))
      return { cells: next }
    }),
}))
