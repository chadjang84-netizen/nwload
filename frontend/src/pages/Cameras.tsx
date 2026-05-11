import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Wifi, WifiOff, Pencil, X, Check, AlertTriangle } from 'lucide-react'
import { fetchCameras, createCamera, deleteCamera, updateCamera, fetchMappings, createMapping, deleteMapping, updateMapping, fetchCommandLog } from '@/api/cameras'
import { fetchDeviceHistory } from '@/api/history'
import type { CameraEntry, MappingEntry, CameraCommandLog } from '@/types'
import { format } from 'date-fns'

export function Cameras() {
  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold" style={{ color: 'var(--color-text-primary)' }}>Camera Management</h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>ONVIF camera registration and device mapping</p>
      </div>
      <CameraRegistry />
      <DeviceMappings />
      <UnmanagedDeviceLog />
      <OnvifCommandLog />
    </div>
  )
}

// ── 공통 ─────────────────────────────────────────────────────────────────────

const inputCls = 'rounded-lg px-3 py-2 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-[var(--color-surface2)] border border-[var(--color-border)] text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)]'

function Field({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <div>
      <label className="text-xs font-medium block mb-1" style={{ color: 'var(--color-text-muted)' }}>{label}</label>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} className={inputCls} />
    </div>
  )
}

function Card({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-xl overflow-hidden" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
      <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: '1px solid var(--color-border)' }}>
        <h2 className="text-sm font-bold" style={{ color: '#0f172a' }}>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

// ── 카메라 레지스트리 ─────────────────────────────────────────────────────────

function CameraRegistry() {
  const qc = useQueryClient()
  const { data: cameras = [], isFetching } = useQuery({ queryKey: ['cameras'], queryFn: fetchCameras })
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ cameraId: '', ipAddress: '', onvifPort: 80, username: '', password: '', profileToken: '' })
  const [formError, setFormError] = useState('')

  const addMut = useMutation({
    mutationFn: createCamera,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cameras'] })
      setShowForm(false)
      setForm({ cameraId: '', ipAddress: '', onvifPort: 80, username: '', password: '', profileToken: '' })
      setFormError('')
    },
    onError: (e: Error) => setFormError(e.message),
  })

  const delMut = useMutation({
    mutationFn: deleteCamera,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cameras'] }),
  })

  const editMut = useMutation({
    mutationFn: ({ cameraId, data }: { cameraId: string; data: Parameters<typeof updateCamera>[1] }) =>
      updateCamera(cameraId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cameras'] }),
  })

  const handleAdd = () => {
    if (!form.cameraId || !form.ipAddress || !form.username || !form.password || !form.profileToken) {
      setFormError('All fields are required.')
      return
    }
    setFormError('')
    addMut.mutate(form)
  }

  return (
    <Card
      title="Camera Registry"
      action={
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-1.5 text-sm px-3.5 py-1.5 rounded-xl text-white shadow-sm transition-opacity hover:opacity-90"
          style={{ background: showForm ? '#374151' : 'var(--color-accent)' }}
        >
          {showForm ? 'Cancel' : <><Plus size={13} />Add</>}
        </button>
      }
    >
      {showForm && (
        <div className="px-5 py-4" style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-surface2)' }}>
          {formError && <p className="text-xs text-red-400 mb-3">{formError}</p>}
          <div className="grid grid-cols-3 gap-3 mb-3">
            <Field label="Camera ID"   value={form.cameraId}      onChange={(v) => setForm((f) => ({ ...f, cameraId: v }))} />
            <Field label="IP Address"  value={form.ipAddress}     onChange={(v) => setForm((f) => ({ ...f, ipAddress: v }))} />
            <Field label="ONVIF Port"  value={String(form.onvifPort)} type="number" onChange={(v) => setForm((f) => ({ ...f, onvifPort: Number(v) }))} />
            <Field label="Username"    value={form.username}      onChange={(v) => setForm((f) => ({ ...f, username: v }))} />
            <Field label="Password"    value={form.password}      type="password" onChange={(v) => setForm((f) => ({ ...f, password: v }))} />
            <Field label="Profile Token" value={form.profileToken} onChange={(v) => setForm((f) => ({ ...f, profileToken: v }))} />
          </div>
          <button
            onClick={handleAdd}
            disabled={addMut.isPending}
            className="px-4 py-1.5 rounded-xl text-sm font-medium text-white shadow-sm disabled:opacity-50"
            style={{ background: 'var(--color-accent)' }}
          >
            {addMut.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      )}

      <table className="w-full text-sm">
        <thead style={{ borderBottom: '1px solid var(--color-border)' }}>
          <tr>
            {['Camera ID', 'IP Address', 'Port', 'Username', 'Profile Token', 'Status', ''].map((h) => (
              <th key={h} className="text-left text-xs font-semibold uppercase tracking-wider px-4 py-3"
                  style={{ color: 'var(--color-text-muted)' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isFetching && <tr><td colSpan={7} className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading…</td></tr>}
          {!isFetching && cameras.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>No cameras registered</td></tr>}
          {cameras.map((cam) => (
            <CameraRow
              key={cam.cameraId}
              cam={cam}
              onDelete={() => delMut.mutate(cam.cameraId)}
              onSave={(data) => editMut.mutate({ cameraId: cam.cameraId, data })}
              isSaving={editMut.isPending}
            />
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function CameraRow({ cam, onDelete, onSave, isSaving }: {
  cam: CameraEntry
  onDelete: () => void
  onSave: (data: { ipAddress: string; onvifPort: number; username: string; password?: string; profileToken: string }) => void
  isSaving: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({ ipAddress: cam.ipAddress, onvifPort: cam.onvifPort, username: cam.username, password: '', profileToken: cam.profileToken })

  const handleSave = () => {
    onSave({ ...draft, onvifPort: Number(draft.onvifPort), password: draft.password || undefined })
    setEditing(false)
  }

  if (editing) {
    return (
      <>
        <tr style={{ borderBottom: 'none', background: 'var(--color-surface2)' }}>
          <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>{cam.cameraId}</td>
          <td className="px-4 py-2">
            <input value={draft.ipAddress} onChange={(e) => setDraft((d) => ({ ...d, ipAddress: e.target.value }))}
                   className={inputCls} placeholder="IP Address" />
          </td>
          <td className="px-4 py-2">
            <input type="number" value={draft.onvifPort} onChange={(e) => setDraft((d) => ({ ...d, onvifPort: Number(e.target.value) }))}
                   className={inputCls} style={{ width: '80px' }} />
          </td>
          <td className="px-4 py-2">
            <input value={draft.username} onChange={(e) => setDraft((d) => ({ ...d, username: e.target.value }))}
                   className={inputCls} placeholder="Username" />
          </td>
          <td className="px-4 py-2">
            <input value={draft.profileToken} onChange={(e) => setDraft((d) => ({ ...d, profileToken: e.target.value }))}
                   className={inputCls} placeholder="Profile Token" />
          </td>
          <td className="px-4 py-2" colSpan={2}>
            <div className="flex items-center gap-2">
              <input type="password" value={draft.password} onChange={(e) => setDraft((d) => ({ ...d, password: e.target.value }))}
                     className={inputCls} placeholder="New password (leave blank to keep)" style={{ maxWidth: '200px' }} />
              <button onClick={handleSave} disabled={isSaving}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-white disabled:opacity-50"
                      style={{ background: 'var(--color-accent)' }}>
                <Check size={12} />{isSaving ? 'Saving…' : 'Save'}
              </button>
              <button onClick={() => setEditing(false)}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border"
                      style={{ color: 'var(--color-text-secondary)', borderColor: 'var(--color-border)' }}>
                <X size={12} />Cancel
              </button>
            </div>
          </td>
        </tr>
      </>
    )
  }

  return (
    <tr className="transition-colors" style={{ borderBottom: '1px solid var(--color-border)' }}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-surface2)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
      <td className="px-4 py-2.5 font-mono text-xs" style={{ color: 'var(--color-text-primary)' }}>{cam.cameraId}</td>
      <td className="px-4 py-2.5 font-mono text-xs" style={{ color: 'var(--color-text-secondary)' }}>{cam.ipAddress}</td>
      <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--color-text-secondary)' }}>{cam.onvifPort}</td>
      <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--color-text-secondary)' }}>{cam.username}</td>
      <td className="px-4 py-2.5 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>{cam.profileToken}</td>
      <td className="px-4 py-2.5">
        <span className="inline-flex items-center gap-1 text-xs font-semibold"
              style={{ color: cam.isReachable ? '#4ade80' : '#4b5563' }}>
          {cam.isReachable ? <Wifi size={12} /> : <WifiOff size={12} />}
          {cam.isReachable ? 'Connected' : 'Unreachable'}
        </span>
      </td>
      <td className="px-4 py-2.5">
        <div className="flex items-center gap-2">
          <button onClick={() => setEditing(true)} className="transition-colors" style={{ color: 'var(--color-text-muted)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-accent)')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-muted)')}>
            <Pencil size={14} />
          </button>
          <button onClick={onDelete} className="transition-colors" style={{ color: 'var(--color-text-muted)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = '#f87171')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-muted)')}>
            <Trash2 size={14} />
          </button>
        </div>
      </td>
    </tr>
  )
}

// ── 단말-카메라 매핑 ──────────────────────────────────────────────────────────

function DeviceMappings() {
  const qc = useQueryClient()
  const { data: mappings = [], isFetching } = useQuery({ queryKey: ['mappings'], queryFn: fetchMappings })
  const [routerCtn, setRouterCtn] = useState('')
  const [cameraId, setCameraId] = useState('')
  const [formError, setFormError] = useState('')

  const addMut = useMutation({
    mutationFn: ({ ctn, cam }: { ctn: string; cam: string }) => createMapping(ctn, cam),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['mappings'] }); setRouterCtn(''); setCameraId(''); setFormError('') },
    onError: (e: Error) => setFormError(e.message),
  })

  const delMut = useMutation({
    mutationFn: deleteMapping,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mappings'] }),
  })

  const editMut = useMutation({
    mutationFn: ({ ctn, cam }: { ctn: string; cam: string }) => updateMapping(ctn, cam),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['mappings'] }),
  })

  const handleAdd = () => {
    if (!routerCtn || !cameraId) { setFormError('Router CTN and Camera ID are required.'); return }
    setFormError('')
    addMut.mutate({ ctn: routerCtn, cam: cameraId })
  }

  return (
    <Card title="Device-Camera Mapping">
      <div className="px-5 py-4" style={{ borderBottom: '1px solid var(--color-border)', background: 'var(--color-surface2)' }}>
        {formError && <p className="text-xs text-red-400 mb-2">{formError}</p>}
        <div className="flex gap-3 items-end">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>Router CTN</label>
            <input value={routerCtn} onChange={(e) => setRouterCtn(e.target.value)} placeholder="e.g. [MASKED_PHONE_NUMBER]"
                   className={inputCls + ' w-44'} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>Camera ID</label>
            <input value={cameraId} onChange={(e) => setCameraId(e.target.value)} placeholder="e.g. CAM-001"
                   className={inputCls + ' w-40'} />
          </div>
          <button onClick={handleAdd} disabled={addMut.isPending}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium text-white shadow-sm disabled:opacity-50 transition-opacity hover:opacity-90"
                  style={{ background: 'var(--color-accent)' }}>
            <Plus size={13} />
            {addMut.isPending ? 'Adding…' : 'Add Mapping'}
          </button>
        </div>
      </div>

      <table className="w-full text-sm">
        <thead style={{ borderBottom: '1px solid var(--color-border)' }}>
          <tr>
            {['Router CTN', 'Camera IDs', ''].map((h) => (
              <th key={h} className="text-left text-xs font-semibold uppercase tracking-wider px-4 py-3"
                  style={{ color: 'var(--color-text-muted)' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isFetching && <tr><td colSpan={3} className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading…</td></tr>}
          {!isFetching && mappings.length === 0 && <tr><td colSpan={3} className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>No mappings</td></tr>}
          {mappings.map((m) => (
            <MappingRow
              key={m.routerCtn}
              mapping={m}
              onDelete={() => delMut.mutate(m.routerCtn)}
              onSave={(cam) => editMut.mutate({ ctn: m.routerCtn, cam })}
              isSaving={editMut.isPending}
            />
          ))}
        </tbody>
      </table>
    </Card>
  )
}

function MappingRow({ mapping, onDelete, onSave, isSaving }: {
  mapping: MappingEntry
  onDelete: () => void
  onSave: (cameraId: string) => void
  isSaving: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draftCamId, setDraftCamId] = useState(mapping.cameraIds[0] ?? '')

  const handleSave = () => {
    if (!draftCamId.trim()) return
    onSave(draftCamId.trim())
    setEditing(false)
  }

  return (
    <tr className="transition-colors" style={{ borderBottom: '1px solid var(--color-border)' }}
        onMouseEnter={(e) => { if (!editing) e.currentTarget.style.background = 'var(--color-surface2)' }}
        onMouseLeave={(e) => { if (!editing) e.currentTarget.style.background = 'transparent' }}>
      <td className="px-4 py-2.5 font-mono text-xs" style={{ color: 'var(--color-text-secondary)' }}>{mapping.routerCtn}</td>
      <td className="px-4 py-2.5">
        {editing ? (
          <input value={draftCamId} onChange={(e) => setDraftCamId(e.target.value)}
                 className={inputCls} style={{ maxWidth: '180px' }} placeholder="Camera ID" />
        ) : (
          <div className="flex flex-wrap gap-1">
            {mapping.cameraIds.map((id) => (
              <span key={id} className="text-xs rounded-lg px-2 py-0.5 font-mono"
                    style={{ background: '#eff6ff', color: '#2563eb' }}>{id}</span>
            ))}
          </div>
        )}
      </td>
      <td className="px-4 py-2.5">
        {editing ? (
          <div className="flex items-center gap-2">
            <button onClick={handleSave} disabled={isSaving}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-white disabled:opacity-50"
                    style={{ background: 'var(--color-accent)' }}>
              <Check size={12} />{isSaving ? 'Saving…' : 'Save'}
            </button>
            <button onClick={() => { setEditing(false); setDraftCamId(mapping.cameraIds[0] ?? '') }}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border"
                    style={{ color: 'var(--color-text-secondary)', borderColor: 'var(--color-border)' }}>
              <X size={12} />Cancel
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <button onClick={() => { setDraftCamId(mapping.cameraIds[0] ?? ''); setEditing(true) }}
                    className="transition-colors" style={{ color: 'var(--color-text-muted)' }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-accent)')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-muted)')}>
              <Pencil size={14} />
            </button>
            <button onClick={onDelete} className="transition-colors" style={{ color: 'var(--color-text-muted)' }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#f87171')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-muted)')}>
              <Trash2 size={14} />
            </button>
          </div>
        )}
      </td>
    </tr>
  )
}

// ── 미매핑 단말 이력 ──────────────────────────────────────────────────────────

function UnmanagedDeviceLog() {
  const { data: allHistory = [], isFetching } = useQuery({
    queryKey: ['history-devices-unmanaged'],
    queryFn: () => fetchDeviceHistory({}),
    refetchInterval: 10000,
  })

  const logs = allHistory.filter((e) => (e as unknown as { eventType?: string }).eventType === 'DEVICE_UNMANAGED')

  return (
    <Card title="Unmanaged Device Log">
      <div className="px-5 py-3" style={{ borderBottom: '1px solid var(--color-border)', background: '#fffbeb' }}>
        <div className="flex items-center gap-2 text-xs" style={{ color: '#92400e' }}>
          <AlertTriangle size={13} />
          <span>Devices with no camera mapping. Contact the vendor with the CTN below to register ONVIF camera information.</span>
        </div>
      </div>
      <table className="w-full text-sm">
        <thead style={{ borderBottom: '1px solid var(--color-border)' }}>
          <tr>
            {['Time', 'Router CTN', 'Previous State', 'Message'].map((h) => (
              <th key={h} className="text-left text-xs font-semibold uppercase tracking-wider px-4 py-3"
                  style={{ color: 'var(--color-text-muted)' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isFetching && logs.length === 0 && (
            <tr><td colSpan={4} className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading…</td></tr>
          )}
          {!isFetching && logs.length === 0 && (
            <tr><td colSpan={4} className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>No unmanaged devices detected</td></tr>
          )}
          {logs.map((log, i) => {
            const raw = log as unknown as { eventType: string; timestamp: string; routerCtn?: string; previousState?: string; message?: string }
            return (
              <tr key={i} className="transition-colors"
                  style={{ borderBottom: '1px solid var(--color-border)', background: i % 2 === 0 ? 'transparent' : 'var(--color-surface2)' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#fef9c3')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = i % 2 === 0 ? 'transparent' : 'var(--color-surface2)')}>
                <td className="px-4 py-2.5 font-mono text-xs whitespace-nowrap" style={{ color: 'var(--color-text-muted)' }}>
                  {formatTs(raw.timestamp)}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {raw.routerCtn ?? '—'}
                </td>
                <td className="px-4 py-2.5 text-xs">
                  <span className="px-2 py-0.5 rounded-full text-xs font-semibold"
                        style={{ background: '#fee2e2', color: '#dc2626' }}>
                    {raw.previousState ?? 'UNMANAGED'}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {raw.message ?? '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </Card>
  )
}

function formatTs(ts: string) {
  try { return format(new Date(ts), 'yyyy-MM-dd HH:mm:ss') } catch { return ts }
}

// ── ONVIF 커맨드 이력 ────────────────────────────────────────────────────────

const profileBadge: Record<string, { bg: string; color: string }> = {
  DEFAULT:  { bg: '#f1f5f9', color: '#64748b' },
  NORMAL:   { bg: '#dcfce7', color: '#16a34a' },
  STEP_UP:  { bg: '#fef9c3', color: '#ca8a04' },
  DEGRADED: { bg: '#fee2e2', color: '#dc2626' },
}

function fmtBitrate(bps: number) { return `${(bps / 1000).toFixed(0)}kbps` }
function fmtRes(r: [number, number]) { return `${r[0]}×${r[1]}` }
function fmtTs(ts: string) {
  try { return format(new Date(ts), 'HH:mm:ss') } catch { return ts }
}

interface DeviceQualityHistory {
  routerCtn: string
  cameraId: string | null
  entries: CameraCommandLog[]
}

function OnvifCommandLog() {
  const [view, setView] = useState<'device' | 'raw'>('device')

  const { data: logs = [] } = useQuery({
    queryKey: ['command-log'],
    queryFn: fetchCommandLog,
    refetchInterval: 3000,
  })

  const byDevice = new Map<string, DeviceQualityHistory>()
  ;[...logs].reverse().forEach((log) => {
    const key = log.routerCtn
    if (!byDevice.has(key)) byDevice.set(key, { routerCtn: log.routerCtn, cameraId: log.cameraId, entries: [] })
    byDevice.get(key)!.entries.push(log)
  })
  const deviceList = Array.from(byDevice.values())

  return (
    <Card
      title="ONVIF Command Log"
      action={
        <div className="flex gap-1">
          {(['device', 'raw'] as const).map((v) => (
            <button key={v} onClick={() => setView(v)}
                    className="text-xs px-3 py-1.5 rounded-xl border transition-all"
                    style={view === v
                      ? { background: 'var(--color-accent)', color: '#fff', borderColor: 'var(--color-accent)' }
                      : { background: 'transparent', color: 'var(--color-text-secondary)', borderColor: 'var(--color-border)' }}>
              {v === 'device' ? 'Per-Device Quality' : 'Raw Log'}
            </button>
          ))}
        </div>
      }
    >
      {view === 'device' ? (
        <div className="p-5 space-y-3">
          {deviceList.length === 0 && (
            <p className="text-sm text-center py-8" style={{ color: 'var(--color-text-muted)' }}>No history — configure device-camera mappings and run a simulation.</p>
          )}
          {deviceList.map((d) => <DeviceQualityCard key={d.routerCtn} dev={d} />)}
        </div>
      ) : (
        <RawLogTable logs={logs} />
      )}
    </Card>
  )
}

function DeviceQualityCard({ dev }: { dev: DeviceQualityHistory }) {
  const defaultEntry = dev.entries.find((e) => e.command === 'GetVideoEncoderConfiguration')
  const setEntries   = dev.entries.filter((e) => e.command === 'SetVideoEncoderConfiguration')
  const latest       = setEntries[setEntries.length - 1]
  const currentProfile = latest?.profile ?? 'DEFAULT'
  const isDegraded  = currentProfile === 'DEGRADED'
  const isRestored  = currentProfile === 'NORMAL'

  const pb = profileBadge[currentProfile] ?? profileBadge.DEFAULT

  const cardBorder = isDegraded ? '#fca5a5' : currentProfile === 'STEP_UP' ? '#fcd34d' : isRestored ? '#86efac' : 'var(--color-border)'
  const cardBg     = isDegraded ? '#fef2f2' : currentProfile === 'STEP_UP' ? '#fffbeb' : isRestored ? '#f0fdf4' : 'var(--color-surface2)'

  return (
    <div className="rounded-2xl border p-4" style={{ borderColor: cardBorder, background: cardBg }}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <span className="font-mono text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>{dev.routerCtn}</span>
          {dev.cameraId
            ? <span className="ml-2 text-xs font-mono" style={{ color: 'var(--color-text-muted)' }}>{dev.cameraId}</span>
            : <span className="ml-2 text-xs font-semibold px-1.5 py-0.5 rounded" style={{ background: '#fee2e2', color: '#dc2626' }}>No camera mapping</span>
          }
        </div>
        <span className="text-xs font-bold px-2.5 py-0.5 rounded-full" style={{ background: pb.bg, color: pb.color }}>
          Current: {currentProfile}
        </span>
      </div>

      {defaultEntry && (
        <div className="mb-2 px-3 py-2 rounded-xl text-xs flex gap-4 items-center"
             style={{ background: 'var(--color-surface2)', color: 'var(--color-text-muted)', border: '1px solid var(--color-border)' }}>
          <span className="font-semibold" style={{ color: 'var(--color-text-secondary)' }}>Default</span>
          <span>{fmtBitrate(defaultEntry.bitrate)}</span>
          <span>{defaultEntry.framerate}fps</span>
          <span>{fmtRes(defaultEntry.resolution)}</span>
          <span className="ml-auto">{fmtTs(defaultEntry.timestamp)}</span>
        </div>
      )}

      {setEntries.length > 0 && (
        <div className="space-y-1">
          {setEntries.map((e, i) => {
            const prev = i === 0 ? defaultEntry : setEntries[i - 1]
            const arrow = prev && prev.profile !== e.profile ? `${prev.profile} → ${e.profile}` : e.profile
            const epb = profileBadge[e.profile] ?? profileBadge.DEFAULT
            return (
              <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-xl text-xs border"
                   style={!e.success
                     ? { borderColor: '#fca5a5', background: '#fef2f222' }
                     : { borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}>
                <span className="font-semibold px-2 py-0.5 rounded-full" style={{ background: epb.bg, color: epb.color }}>{arrow}</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>{fmtBitrate(e.bitrate)}</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>{e.framerate}fps</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>{fmtRes(e.resolution)}</span>
                <span className="ml-auto" style={{ color: 'var(--color-text-muted)' }}>{fmtTs(e.timestamp)}</span>
                {!e.success && <span className="font-semibold" style={{ color: '#f87171' }}>Failed</span>}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function RawLogTable({ logs }: { logs: CameraCommandLog[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead style={{ borderBottom: '1px solid var(--color-border)' }}>
          <tr>
            {['Time', 'Camera ID', 'Router CTN', 'Command', 'Profile', 'Bitrate', 'FPS', 'Resolution', 'Result'].map((h) => (
              <th key={h} className="text-left text-xs font-semibold uppercase tracking-wider px-4 py-3 whitespace-nowrap"
                  style={{ color: 'var(--color-text-muted)' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {logs.length === 0 && <tr><td colSpan={9} className="text-center py-8 text-sm" style={{ color: 'var(--color-text-muted)' }}>No history</td></tr>}
          {logs.map((log, i) => {
            const isGet = log.command === 'GetVideoEncoderConfiguration'
            const pb = profileBadge[log.profile] ?? profileBadge.DEFAULT
            return (
              <tr key={i} className="transition-colors"
                  style={{ borderBottom: '1px solid var(--color-border)', background: !log.success ? '#fef2f222' : 'transparent' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = !log.success ? '#fef2f244' : 'var(--color-surface2)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = !log.success ? '#fef2f222' : 'transparent')}>
                <td className="px-4 py-2.5 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>{fmtTs(log.timestamp)}</td>
                <td className="px-4 py-2.5 font-mono text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                  {log.cameraId ?? <span style={{ color: '#f87171' }} className="font-semibold not-italic">No mapping</span>}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>{log.routerCtn}</td>
                <td className="px-4 py-2.5">
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                        style={isGet ? { background: '#eff6ff', color: '#2563eb' } : { background: '#f5f3ff', color: '#7c3aed' }}>
                    {isGet ? 'GET' : 'SET'}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ background: pb.bg, color: pb.color }}>{log.profile}</span>
                </td>
                <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--color-text-secondary)' }}>{fmtBitrate(log.bitrate)}</td>
                <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--color-text-secondary)' }}>{log.framerate}fps</td>
                <td className="px-4 py-2.5 text-xs" style={{ color: 'var(--color-text-secondary)' }}>{fmtRes(log.resolution)}</td>
                <td className="px-4 py-2.5">
                  {log.success
                    ? <span className="text-xs font-semibold" style={{ color: '#4ade80' }}>OK</span>
                    : <span className="text-xs font-semibold" style={{ color: '#f87171' }} title={log.error}>Failed</span>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
