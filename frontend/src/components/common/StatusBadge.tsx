import type { CellState, DeviceState } from '@/types'

const cellStyle: Record<CellState, { bg: string; text: string; dot: string; label: string }> = {
  NORMAL:     { bg: '#dcfce7', text: '#16a34a', dot: '#22c55e', label: 'Normal' },
  WARNING:    { bg: '#fef9c3', text: '#ca8a04', dot: '#eab308', label: 'Warning' },
  CONGESTION: { bg: '#ffedd5', text: '#ea580c', dot: '#f97316', label: 'Congestion' },
  OVERLOAD:   { bg: '#fee2e2', text: '#dc2626', dot: '#ef4444', label: 'Overload' },
}

const deviceStyle: Record<DeviceState, { bg: string; text: string; dot: string; label: string }> = {
  NORMAL:           { bg: '#dcfce7', text: '#16a34a', dot: '#22c55e', label: 'Normal' },
  DEGRADED:         { bg: '#fee2e2', text: '#dc2626', dot: '#ef4444', label: 'Degraded' },
  RECOVERY_PENDING: { bg: '#ede9fe', text: '#7c3aed', dot: '#8b5cf6', label: 'Recovery' },
  UNMANAGED:        { bg: '#fef9c3', text: '#ca8a04', dot: '#eab308', label: 'Unmanaged' },
}

export function CellStateBadge({ state }: { state: CellState }) {
  const s = cellStyle[state]
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold"
          style={{ background: s.bg, color: s.text }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.dot }} />
      {s.label}
    </span>
  )
}

export function DeviceStateBadge({ state }: { state: DeviceState }) {
  const s = deviceStyle[state]
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold"
          style={{ background: s.bg, color: s.text }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.dot }} />
      {s.label}
    </span>
  )
}
