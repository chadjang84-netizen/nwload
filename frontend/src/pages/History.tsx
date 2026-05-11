import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Download, Search, RefreshCw, Trash2 } from 'lucide-react'
import Papa from 'papaparse'
import { fetchDeviceHistory, fetchCellHistory, resetHistory, fetchHistoryStats } from '@/api/history'
import type { CellHistoryItem } from '@/types'
import { DeviceStateBadge, CellStateBadge } from '@/components/common/StatusBadge'

const profileStyle: Record<string, { color: string; bg: string }> = {
  NORMAL:   { color: '#16a34a', bg: '#dcfce7' },
  STEP_UP:  { color: '#ca8a04', bg: '#fef9c3' },
  DEGRADED: { color: '#dc2626', bg: '#fee2e2' },
}

const cellEventStyle: Record<string, { bg: string; border: string; labelBg: string; labelColor: string; label: string }> = {
  CELL_OVERLOAD: { bg: '#fef2f2', border: '#ef4444', labelBg: '#fee2e2', labelColor: '#dc2626', label: 'OVERLOAD' },
  CELL_RECOVERY: { bg: '#f0fdf4', border: '#22c55e', labelBg: '#dcfce7', labelColor: '#16a34a', label: 'RECOVERY' },
}

function ResetButton() {
  const qc = useQueryClient()
  const [confirm, setConfirm] = useState(false)
  const { data: stats } = useQuery({ queryKey: ['history-stats'], queryFn: fetchHistoryStats, refetchInterval: 30000 })
  const mutation = useMutation({
    mutationFn: resetHistory,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['history-devices'] })
      qc.invalidateQueries({ queryKey: ['history-cells'] })
      qc.invalidateQueries({ queryKey: ['history-stats'] })
      setConfirm(false)
    },
  })

  const fmt = (bytes: number) =>
    bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(2)} MB`

  return (
    <div className="flex items-center gap-3">
      {stats && (
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {stats.rows.toLocaleString()} rows · {fmt(stats.bytes)}
        </span>
      )}
      {confirm ? (
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium" style={{ color: '#dc2626' }}>Delete all history?</span>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="px-3 py-1 rounded-lg text-xs font-semibold text-white disabled:opacity-50"
            style={{ background: '#dc2626' }}
          >
            {mutation.isPending ? 'Deleting…' : 'Confirm'}
          </button>
          <button
            onClick={() => setConfirm(false)}
            className="px-3 py-1 rounded-lg text-xs"
            style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)', background: 'var(--color-surface)' }}
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          onClick={() => setConfirm(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
          style={{ border: '1px solid #fca5a5', color: '#dc2626', background: '#fef2f2' }}
        >
          <Trash2 size={12} /> Reset DB
        </button>
      )}
    </div>
  )
}

export function History() {
  return (
    <div className="p-6 flex flex-col gap-4 h-full min-h-0">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold" style={{ color: '#0f172a' }}>History</h1>
        <ResetButton />
      </div>
      <div className="flex gap-5 flex-1 min-h-0">
        <div className="flex-1 min-w-0">
          <DeviceHistory />
        </div>
        <div className="flex-1 min-w-0">
          <CellHistory />
        </div>
      </div>
    </div>
  )
}

function DeviceHistory() {
  const [ctn, setCtn] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [submitted, setSubmitted] = useState<{ ctn: string; from: string; to: string } | null>(null)

  const { data = [], isFetching } = useQuery({
    queryKey: ['history-devices', submitted],
    queryFn: () => fetchDeviceHistory({
      ctn: submitted?.ctn || undefined,
      from: submitted?.from || undefined,
      to: submitted?.to || undefined,
    }),
    enabled: submitted !== null,
  })

  const handleSearch = () => setSubmitted({ ctn, from, to })

  const handleCSV = () => {
    const csv = Papa.unparse(data.map((d) => ({
      Router_CTN: d.routerCtn,
      Prev_State: d.previousState,
      New_State: d.newState,
      Action: d.action ?? '-',
      Timestamp: d.timestamp,
      Quality: d.profile,
    })))
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'device_history.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold" style={{ color: '#0f172a' }}>Device State History</h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>Device state change history</p>
        </div>
        {data.length > 0 && (
          <button
            onClick={handleCSV}
            className="flex items-center gap-2 text-sm px-3.5 py-2 rounded-lg transition-colors"
            style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)', background: 'var(--color-surface)' }}
          >
            <Download size={14} /> Export CSV
          </button>
        )}
      </div>

      <div className="rounded-xl p-4" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
        <div className="flex flex-wrap gap-3 items-end">
          <Field label="Router CTN">
            <input value={ctn} onChange={(e) => setCtn(e.target.value)}
                   placeholder="e.g. [MASKED_PHONE_NUMBER]" className={inputCls} />
          </Field>
          <Field label="From">
            <input type="datetime-local" value={from} onChange={(e) => setFrom(e.target.value)} className={inputCls} />
          </Field>
          <Field label="To">
            <input type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)} className={inputCls} />
          </Field>
          <button
            onClick={handleSearch}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-opacity hover:opacity-90"
            style={{ background: 'var(--color-accent)' }}
          >
            <Search size={14} /> Search
          </button>
        </div>
      </div>

      <div className="rounded-xl overflow-hidden flex-1 min-h-0" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
        <div className="overflow-auto h-full">
          <table className="w-full text-sm">
            <thead style={{ position: 'sticky', top: 0, zIndex: 1, background: '#f8fafc', borderBottom: '1px solid var(--color-border)' }}>
              <tr>
                {['Router CTN', 'Prev State', 'New State', 'Action', 'Timestamp', 'Quality'].map((h) => (
                  <th key={h} className="text-left text-xs font-semibold uppercase tracking-wider px-4 py-3"
                      style={{ color: 'var(--color-text-muted)' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isFetching && (
                <tr><td colSpan={6} className="text-center py-10" style={{ color: 'var(--color-text-muted)' }}>Loading…</td></tr>
              )}
              {!isFetching && data.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center py-10 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                    {submitted ? 'No results found' : 'Enter search criteria above and click Search'}
                  </td>
                </tr>
              )}
              {data.map((row, i) => {
                const ps = profileStyle[row.profile]
                return (
                  <tr key={i} className="transition-colors"
                      style={{ borderBottom: '1px solid var(--color-border)' }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-surface2)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
                    <td className="px-4 py-2.5 font-mono text-xs" style={{ color: 'var(--color-text-secondary)' }}>{row.routerCtn}</td>
                    <td className="px-4 py-2.5"><DeviceStateBadge state={row.previousState} /></td>
                    <td className="px-4 py-2.5"><DeviceStateBadge state={row.newState} /></td>
                    <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--color-text-muted)' }}>{row.action ?? '—'}</td>
                    <td className="px-4 py-2.5 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>
                      {format(new Date(row.timestamp), 'yyyy-MM-dd HH:mm:ss')}
                    </td>
                    <td className="px-4 py-2.5">
                      {ps
                        ? <span className="px-2 py-0.5 rounded-md text-xs font-semibold" style={{ background: ps.bg, color: ps.color }}>{row.profile}</span>
                        : <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{row.profile}</span>
                      }
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function CellHistory() {
  const [ecgiInput, setEcgiInput] = useState('')
  const [bandInput, setBandInput] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [submitted, setSubmitted] = useState<{ ecgi?: number; band?: number; from: string; to: string }>({from: '', to: ''})

  const { data = [], isFetching, refetch } = useQuery({
    queryKey: ['history-cells', submitted],
    queryFn: () => fetchCellHistory({
      ecgi: submitted.ecgi,
      band: submitted.band,
      from: submitted.from || undefined,
      to: submitted.to || undefined,
    }),
    refetchInterval: 10000,
  })

  const handleSearch = () => setSubmitted({
    ecgi: ecgiInput ? parseInt(ecgiInput, 10) : undefined,
    band: bandInput ? parseInt(bandInput, 10) : undefined,
    from,
    to,
  })

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold" style={{ color: '#0f172a' }}>Cell State Log</h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>Overload / recovery events</p>
        </div>
        <button
          onClick={() => refetch()}
          className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors"
          style={{ border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text-secondary)' }}
          title="Refresh"
        >
          <RefreshCw size={13} />
        </button>
      </div>

      <div className="rounded-xl p-4" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <Field label="ECGI">
              <input value={ecgiInput} onChange={(e) => setEcgiInput(e.target.value)}
                     placeholder="e.g. 100001" className={inputCls + ' w-full'} />
            </Field>
            <Field label="Band">
              <input value={bandInput} onChange={(e) => setBandInput(e.target.value)}
                     placeholder="e.g. 78" className={inputCls + ' w-full'} />
            </Field>
          </div>
          <div className="flex gap-2">
            <Field label="From">
              <input type="datetime-local" value={from} onChange={(e) => setFrom(e.target.value)} className={inputCls + ' w-full'} />
            </Field>
            <Field label="To">
              <input type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)} className={inputCls + ' w-full'} />
            </Field>
          </div>
          <button
            onClick={handleSearch}
            className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-opacity hover:opacity-90 w-full"
            style={{ background: 'var(--color-accent)' }}
          >
            <Search size={14} /> Search
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto space-y-3 pr-1">
        {isFetching && (
          <p className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading…</p>
        )}
        {!isFetching && data.length === 0 && (
          <p className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>No cell events</p>
        )}
        {!isFetching && groupByCells(data).map((group) => (
          <CellCard key={`${group.ecgi}:${group.band}`} group={group} />
        ))}
      </div>
    </div>
  )
}

interface CellGroup {
  ecgi: number
  band: number
  events: CellHistoryItem[]  // newest first
}

function groupByCells(items: CellHistoryItem[]): CellGroup[] {
  const map = new Map<string, CellGroup>()
  for (const item of items) {
    const key = `${item.ecgi}:${item.band}`
    if (!map.has(key)) map.set(key, { ecgi: item.ecgi, band: item.band, events: [] })
    map.get(key)!.events.push(item)
  }
  // sort cells: most recent event first
  return Array.from(map.values()).sort(
    (a, b) => new Date(b.events[0].timestamp).getTime() - new Date(a.events[0].timestamp).getTime()
  )
}

function CellCard({ group }: { group: CellGroup }) {
  const latest = group.events[0]
  const currentState = latest.eventType === 'CELL_OVERLOAD' ? 'OVERLOAD' : 'NORMAL'
  const isOverload = currentState === 'OVERLOAD'

  const cardBorder = isOverload ? '#fca5a5' : '#86efac'
  const cardBg     = isOverload ? '#fef2f2' : '#f0fdf4'

  return (
    <div className="rounded-xl border p-4" style={{ borderColor: cardBorder, background: cardBg }}>
      {/* Card header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-bold" style={{ color: '#0f172a' }}>
            ECGI {group.ecgi}
          </span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold"
                style={{ background: '#eff6ff', color: '#2563eb' }}>
            B{group.band}
          </span>
        </div>
        <CellStateBadge state={currentState as 'OVERLOAD' | 'NORMAL'} />
      </div>

      {/* State change timeline */}
      <div className="space-y-1.5">
        {group.events.map((item) => {
          const s = cellEventStyle[item.eventType] ?? cellEventStyle.CELL_OVERLOAD
          const prevState = item.eventType === 'CELL_OVERLOAD' ? 'NORMAL' : 'OVERLOAD'
          const nextState = item.eventType === 'CELL_OVERLOAD' ? 'OVERLOAD' : 'NORMAL'
          return (
            <div key={item.id}
                 className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs border"
                 style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}>
              <span className="font-bold px-1.5 py-0.5 rounded text-[10px] shrink-0"
                    style={{ background: s.labelBg, color: s.labelColor }}>
                {prevState} → {nextState}
              </span>
              <span className="ml-auto font-mono shrink-0" style={{ color: 'var(--color-text-muted)' }}>
                {format(new Date(item.timestamp), 'yyyy-MM-dd HH:mm:ss')}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const inputCls = 'rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 w-44'
  + ' bg-[var(--color-surface2)] border border-[var(--color-border)] text-[var(--color-text-primary)]'

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1 flex-1">
      <label className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>{label}</label>
      {children}
    </div>
  )
}
