import { format } from 'date-fns'
import { useAlertStore } from '@/store/alertStore'
import type { AlertEventType } from '@/types'

const eventLabel: Record<AlertEventType, string> = {
  CELL_OVERLOAD:    'Cell Overload',
  CELL_RECOVERY:    'Cell Recovery',
  DEVICE_DEGRADED:  'Quality Degraded',
  DEVICE_RESTORED:  'Quality Restored',
  DEVICE_UNMANAGED: 'Unmanaged Device',
}

const eventStyle: Record<AlertEventType, { border: string; bg: string; dot: string; label: string; labelBg: string; labelColor: string }> = {
  CELL_OVERLOAD:    { border: '#ef4444', bg: '#fef2f2', dot: '#ef4444', label: 'CRIT', labelBg: '#fee2e2', labelColor: '#dc2626' },
  CELL_RECOVERY:    { border: '#22c55e', bg: '#f0fdf4', dot: '#22c55e', label: 'OK',   labelBg: '#dcfce7', labelColor: '#16a34a' },
  DEVICE_DEGRADED:  { border: '#f97316', bg: '#fff7ed', dot: '#f97316', label: 'WARN', labelBg: '#ffedd5', labelColor: '#ea580c' },
  DEVICE_RESTORED:  { border: '#6366f1', bg: '#f5f3ff', dot: '#818cf8', label: 'OK',   labelBg: '#ede9fe', labelColor: '#7c3aed' },
  DEVICE_UNMANAGED: { border: '#f59e0b', bg: '#fffbeb', dot: '#f59e0b', label: 'WARN', labelBg: '#fef9c3', labelColor: '#ca8a04' },
}

const filters: Array<{ value: AlertEventType | 'ALL'; label: string }> = [
  { value: 'ALL',              label: 'All' },
  { value: 'CELL_OVERLOAD',    label: 'Cell Overload' },
  { value: 'CELL_RECOVERY',    label: 'Cell Recovery' },
  { value: 'DEVICE_DEGRADED',  label: 'Degraded' },
  { value: 'DEVICE_RESTORED',  label: 'Restored' },
  { value: 'DEVICE_UNMANAGED', label: 'Unmanaged' },
]

export function AlertFeed() {
  const { alerts, filter, setFilter, clearAll } = useAlertStore()
  const visible = filter === 'ALL' ? alerts : alerts.filter((a) => a.eventType === filter)

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--color-surface)' }}>
      <div className="flex items-center justify-between px-4 py-3"
           style={{ borderBottom: '1px solid var(--color-border)' }}>
        <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
          Alert Feed
        </h3>
        <button
          onClick={clearAll}
          className="text-xs transition-colors hover:text-red-500"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Clear all
        </button>
      </div>

      <div className="flex gap-1.5 px-3 py-2.5 flex-wrap"
           style={{ borderBottom: '1px solid var(--color-border)' }}>
        {filters.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className="text-xs px-2.5 py-0.5 rounded-md transition-all"
            style={filter === f.value
              ? { background: 'var(--color-accent)', color: '#fff' }
              : { background: 'var(--color-surface2)', color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)' }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2 min-h-0">
        {visible.length === 0 && (
          <div className="text-center text-sm py-8" style={{ color: 'var(--color-text-muted)' }}>
            No alerts
          </div>
        )}
        {visible.map((alert) => {
          const s = eventStyle[alert.eventType]
          return (
            <div key={alert.id}
                 className="rounded-lg px-3 py-2.5 text-xs"
                 style={{ background: s.bg, borderLeft: `3px solid ${s.border}` }}>
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold flex items-center gap-2" style={{ color: '#1e293b' }}>
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                        style={{ background: s.labelBg, color: s.labelColor }}>
                    {s.label}
                  </span>
                  {eventLabel[alert.eventType]}
                </span>
                <span className="font-mono" style={{ color: 'var(--color-text-muted)', fontSize: 10 }}>
                  {format(new Date(alert.timestamp), 'HH:mm:ss')}
                </span>
              </div>
              <p className="leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
                {alert.message}
              </p>
              {alert.routerCtn && (
                <span className="font-mono mt-0.5 block" style={{ color: 'var(--color-text-muted)', fontSize: 10 }}>
                  {alert.routerCtn}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
