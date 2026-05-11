import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { X } from 'lucide-react'
import type { CellStatus, CellDeviceDetail } from '@/types'
import { CellStateBadge } from '@/components/common/StatusBadge'
import { fetchCellDevices } from '@/api/cells'

const accentColor: Record<string, string> = {
  NORMAL:     '#22c55e',
  WARNING:    '#eab308',
  CONGESTION: '#f97316',
  OVERLOAD:   '#ef4444',
}

const deviceStateColor: Record<string, string> = {
  NORMAL:           '#16a34a',
  DEGRADED:         '#dc2626',
  RECOVERY_PENDING: '#7c3aed',
  UNMANAGED:        '#ca8a04',
}

const profileColor: Record<string, { bg: string; color: string }> = {
  NORMAL:   { bg: '#dcfce7', color: '#16a34a' },
  STEP_UP:  { bg: '#ffedd5', color: '#ea580c' },
  DEGRADED: { bg: '#fee2e2', color: '#dc2626' },
}

interface Props {
  cell: CellStatus
  overloadEnter: number
  slidingWindowSeconds: number
}

function useTimerPct(nextEvalAt: string | null, windowSeconds: number) {
  const [pct, setPct] = useState(0)

  useEffect(() => {
    if (!nextEvalAt) return
    const tick = () => {
      const now = Date.now()
      const evalMs = new Date(nextEvalAt).getTime()
      const windowMs = windowSeconds * 1000
      const remaining = Math.max(0, evalMs - now)
      setPct(Math.min(100, Math.round(((windowMs - remaining) / windowMs) * 100)))
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [nextEvalAt, windowSeconds])

  return pct
}

export function CellStatusPanel({ cell, overloadEnter, slidingWindowSeconds }: Props) {
  const [open, setOpen] = useState(false)
  const pct = Math.min(100, Math.round((cell.ulRbSum / overloadEnter) * 100))
  const bar = accentColor[cell.state] ?? '#94a3b8'
  const timerPct = useTimerPct(cell.nextEvalAt, slidingWindowSeconds)

  const remainingSec = cell.nextEvalAt
    ? Math.max(0, Math.round((new Date(cell.nextEvalAt).getTime() - Date.now()) / 1000))
    : null

  return (
    <>
      <div
        className="rounded-xl overflow-hidden flex flex-col cursor-pointer transition-shadow hover:shadow-md"
        style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}
        onClick={() => setOpen(true)}
      >
        <div className="flex flex-1">
          {/* Left accent bar */}
          <div className="w-1 shrink-0" style={{ background: bar }} />

          <div className="flex-1 px-2.5 pt-2.5 pb-1.5">
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-mono text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                ECGI {cell.groupingKey.ecgi} · B{cell.groupingKey.band}
              </span>
              <CellStateBadge state={cell.state} />
            </div>

            <div className="flex items-baseline gap-1 mb-1.5">
              <span className="text-lg font-bold leading-none" style={{ color: 'var(--color-text-primary)' }}>
                {cell.ulRbSum.toLocaleString()}
              </span>
              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>UL_RB</span>
            </div>

            {/* UL_RB progress bar */}
            <div className="w-full rounded-full h-1.5" style={{ background: '#f1f5f9' }}>
              <div
                className="h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, background: bar }}
              />
            </div>

            <div className="flex items-center justify-between mt-1 text-xs"
                 style={{ color: 'var(--color-text-muted)' }}>
              <span>{cell.ctnList.length} Devices</span>
              <span>{pct}%</span>
            </div>
          </div>
        </div>

        {/* Option B: 카드 하단 타이머 라인 — 카드 내부 최하단 */}
        <div
          className="h-0.5 mx-1 mb-0.5 overflow-hidden rounded-full"
          style={{ background: '#e2e8f0' }}
          title={remainingSec !== null ? `Next evaluation in ${remainingSec}s` : ''}
        >
          <div
            className="h-full rounded-full transition-all duration-1000"
            style={{ width: `${timerPct}%`, background: '#2563eb', boxShadow: '0 0 3px #2563eb55' }}
          />
        </div>
      </div>

      {open && (
        <CellDeviceModal cell={cell} onClose={() => setOpen(false)} />
      )}
    </>
  )
}

function CellDeviceModal({ cell, onClose }: { cell: CellStatus; onClose: () => void }) {
  const { data: devices = [], isFetching } = useQuery({
    queryKey: ['cell-devices', cell.groupingKey.ecgi, cell.groupingKey.band],
    queryFn: () => fetchCellDevices(cell.groupingKey.ecgi, cell.groupingKey.band),
  })

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(15,23,42,0.4)', backdropFilter: 'blur(3px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="w-full max-w-3xl rounded-2xl overflow-hidden flex flex-col"
        style={{ background: '#fff', border: '1px solid #e2e8f0', boxShadow: '0 20px 60px rgba(0,0,0,0.15)', maxHeight: '80vh' }}
      >
        <div className="flex items-center justify-between px-5 py-4"
             style={{ borderBottom: '1px solid #e2e8f0' }}>
          <div className="flex items-center gap-3">
            <span className="font-mono text-sm font-semibold" style={{ color: '#1e293b' }}>
              ECGI {cell.groupingKey.ecgi} · B{cell.groupingKey.band}
            </span>
            <CellStateBadge state={cell.state} />
            <span className="text-xs" style={{ color: '#94a3b8' }}>{cell.ctnList.length} Devices</span>
          </div>
          <button onClick={onClose} className="transition-colors text-slate-400 hover:text-slate-700">
            <X size={16} />
          </button>
        </div>

        <div className="overflow-auto flex-1">
          <table className="w-full text-sm">
            <thead style={{ borderBottom: '1px solid #e2e8f0', position: 'sticky', top: 0, zIndex: 1, background: '#f8fafc' }}>
              <tr>
                {['Router CTN', 'Band', 'ECGI', 'UL_RB', 'Timestamp', 'Device State', 'Quality Profile'].map((h) => (
                  <th key={h} className="text-left text-xs font-semibold uppercase tracking-wider px-4 py-3"
                      style={{ color: '#94a3b8' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isFetching && (
                <tr><td colSpan={7} className="text-center py-10 text-sm" style={{ color: '#94a3b8' }}>Loading…</td></tr>
              )}
              {!isFetching && devices.length === 0 && (
                <tr><td colSpan={7} className="text-center py-10 text-sm" style={{ color: '#94a3b8' }}>No device data</td></tr>
              )}
              {devices.map((d) => (
                <DeviceDetailRow key={d.routerCtn} d={d} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function DeviceDetailRow({ d }: { d: CellDeviceDetail }) {
  const stateColor = deviceStateColor[d.deviceState] ?? '#64748b'
  const pb = profileColor[d.qualityProfile] ?? { bg: '#f1f5f9', color: '#64748b' }

  return (
    <tr
      className="transition-colors"
      style={{ borderBottom: '1px solid #f1f5f9' }}
      onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <td className="px-4 py-2.5 font-mono text-xs font-semibold" style={{ color: '#1e293b' }}>{d.routerCtn}</td>
      <td className="px-4 py-2.5 text-xs font-mono" style={{ color: '#64748b' }}>B{d.band}</td>
      <td className="px-4 py-2.5 text-xs font-mono" style={{ color: '#64748b' }}>{d.ecgi}</td>
      <td className="px-4 py-2.5 text-xs font-bold" style={{ color: '#1e293b' }}>{d.ulRbUsage.toLocaleString()}</td>
      <td className="px-4 py-2.5 font-mono text-xs" style={{ color: '#94a3b8' }}>
        {format(new Date(d.timestamp), 'HH:mm:ss')}
      </td>
      <td className="px-4 py-2.5">
        <span className="text-xs font-semibold" style={{ color: stateColor }}>{d.deviceState}</span>
      </td>
      <td className="px-4 py-2.5">
        <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
              style={{ background: pb.bg, color: pb.color }}>{d.qualityProfile}</span>
      </td>
    </tr>
  )
}
