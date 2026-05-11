import type { DeviceStatus } from '@/types'
import { DeviceStateBadge } from '@/components/common/StatusBadge'

const profileStyle: Record<string, { color: string; bg: string }> = {
  DEGRADED: { color: '#dc2626', bg: '#fee2e2' },
  STEP_UP:  { color: '#ea580c', bg: '#ffedd5' },
  NORMAL:   { color: '#16a34a', bg: '#dcfce7' },
}

export function DeviceStatusPanel({ device }: { device: DeviceStatus }) {
  const remaining = device.cooldownRemainingSeconds
  const ps = profileStyle[device.currentProfile] ?? { color: '#64748b', bg: '#f1f5f9' }

  return (
    <div className="rounded-xl p-4 flex flex-col gap-3"
         style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
          {device.routerCtn}
        </span>
        <DeviceStateBadge state={device.state} />
      </div>

      <div className="flex items-center gap-2">
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Quality Profile</span>
        <span className="ml-auto px-2.5 py-0.5 rounded-md text-xs font-bold"
              style={{ background: ps.bg, color: ps.color }}>
          {device.currentProfile}
        </span>
      </div>

      {device.state === 'RECOVERY_PENDING' && remaining !== null && (
        <div className="flex items-center gap-2 text-xs rounded-lg px-3 py-1.5"
             style={{ background: '#ede9fe', color: '#7c3aed', border: '1px solid #c4b5fd' }}>
          <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
          Recovery pending — {Math.max(0, Math.ceil(remaining / 60))} min remaining
        </div>
      )}
    </div>
  )
}
