import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, Plus, X, CheckCircle } from 'lucide-react'
import { fetchConfig, saveConfig } from '@/api/config'
import type { Configuration, BandThreshold } from '@/types'

const THRESHOLD_FIELDS: { key: keyof BandThreshold; label: string }[] = [
  { key: 'warning',       label: 'Warning' },
  { key: 'congestion',    label: 'Congestion' },
  { key: 'overloadEnter', label: 'Overload Enter' },
  { key: 'overloadExit',  label: 'Overload Exit' },
]

function validateBand(t: BandThreshold): string[] {
  const errs: string[] = []
  if (t.warning >= t.congestion)         errs.push('Warning must be less than Congestion.')
  if (t.congestion >= t.overloadEnter)   errs.push('Congestion must be less than Overload Enter.')
  if (t.overloadExit >= t.overloadEnter) errs.push('Overload Exit must be less than Overload Enter.')
  return errs
}

export function Config() {
  const qc = useQueryClient()
  const { data: remote } = useQuery({ queryKey: ['config'], queryFn: fetchConfig })
  const [local, setLocal] = useState<Configuration | null>(null)
  const [saved, setSaved] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [newBand, setNewBand] = useState('')

  useEffect(() => { if (remote && !local) setLocal(remote) }, [remote, local])

  const mutation = useMutation({
    mutationFn: saveConfig,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['config'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    },
  })

  if (!local) return <div className="p-6 text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading configuration…</div>

  const validate = (): boolean => {
    const errs: string[] = []
    if (local.thresholds.length === 0) errs.push('At least one band threshold must be configured.')
    for (const t of local.thresholds) validateBand(t).forEach((e) => errs.push(`[Band ${t.band}] ${e}`))
    if (local.recoveryCooldownSeconds <= 0) errs.push('Recovery cooldown must be greater than 0.')
    const dr = local.degradation.degradedRatio
    const sr = local.degradation.stepUpRatio
    if (dr <= 0 || dr >= 1) errs.push('Degraded ratio must be between 0% and 100%.')
    if (sr <= 0 || sr >= 1) errs.push('Step-up ratio must be between 0% and 100%.')
    if (dr >= sr) errs.push('Degraded ratio must be lower than step-up ratio.')
    setErrors(errs)
    return errs.length === 0
  }

  const handleSave = () => { if (validate()) mutation.mutate(local) }

  const setBandField = (band: number, key: keyof BandThreshold, value: number) =>
    setLocal((prev) => prev
      ? { ...prev, thresholds: prev.thresholds.map((t) => t.band === band ? { ...t, [key]: value } : t) }
      : prev)

  const BAND_DEFAULTS: Record<number, Omit<BandThreshold, 'band'>> = {
    1:  { warning:  8000, congestion: 16000, overloadEnter: 25000, overloadExit: 20000 },
    3:  { warning: 10000, congestion: 20000, overloadEnter: 30000, overloadExit: 25000 },
    5:  { warning:  5000, congestion: 10000, overloadEnter: 15000, overloadExit: 12000 },
    7:  { warning: 12000, congestion: 24000, overloadEnter: 36000, overloadExit: 30000 },
    8:  { warning:  6000, congestion: 12000, overloadEnter: 18000, overloadExit: 15000 },
    78: { warning: 15000, congestion: 30000, overloadEnter: 50000, overloadExit: 40000 },
  }

  const addBand = () => {
    const n = parseInt(newBand.trim(), 10)
    if (isNaN(n) || local.thresholds.some((t) => t.band === n)) return
    const defaults = BAND_DEFAULTS[n] ?? { warning: 5000, congestion: 10000, overloadEnter: 15000, overloadExit: 12000 }
    setLocal((prev) => prev
      ? { ...prev, thresholds: [...prev.thresholds, { band: n, ...defaults }].sort((a, b) => a.band - b.band) }
      : prev)
    setNewBand('')
  }

  const removeBand = (band: number) =>
    setLocal((prev) => prev ? { ...prev, thresholds: prev.thresholds.filter((t) => t.band !== band) } : prev)

  const setDegradation = (key: 'degradedRatio' | 'stepUpRatio', pct: number) =>
    setLocal((prev) => prev
      ? { ...prev, degradation: { ...prev.degradation, [key]: pct / 100 } }
      : prev)

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--color-text-primary)' }}>Configuration</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--color-text-secondary)' }}>System thresholds and quality profiles</p>
        </div>
        <div className="flex items-center gap-3">
          {saved && (
            <span className="flex items-center gap-1.5 text-sm font-medium" style={{ color: '#4ade80' }}>
              <CheckCircle size={15} /> Saved
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={mutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-opacity hover:opacity-90"
            style={{ background: 'var(--color-accent)' }}
          >
            <Save size={14} />
            {mutation.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>

      {errors.length > 0 && (
        <div className="rounded-xl border p-4 text-sm space-y-1"
             style={{ borderColor: '#fca5a5', background: '#fef2f2', color: '#dc2626' }}>
          {errors.map((e) => <div key={e} className="flex gap-1.5"><span>•</span>{e}</div>)}
        </div>
      )}

      <Card title="Band Load Thresholds">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                <th className="text-left py-2 pr-4 text-xs font-medium w-24" style={{ color: 'var(--color-text-muted)' }}>Band</th>
                {THRESHOLD_FIELDS.map(({ label }) => (
                  <th key={label} className="text-left py-2 px-2 text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>{label}</th>
                ))}
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {local.thresholds.length === 0 && (
                <tr><td colSpan={6} className="py-6 text-center text-sm" style={{ color: 'var(--color-text-muted)' }}>No bands configured. Add one below.</td></tr>
              )}
              {local.thresholds.map((t) => (
                <tr key={t.band} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td className="py-2 pr-4">
                    <span className="px-2.5 py-1 rounded-md text-xs font-bold"
                          style={{ background: '#eff6ff', color: '#2563eb' }}>
                      B{t.band}
                    </span>
                  </td>
                  {THRESHOLD_FIELDS.map(({ key }) => (
                    <td key={key} className="py-1.5 px-2">
                      <input
                        type="number"
                        value={t[key] as number}
                        onChange={(e) => setBandField(t.band, key, Number(e.target.value))}
                        className={numInputCls}
                      />
                    </td>
                  ))}
                  <td className="py-1 text-center">
                    <button onClick={() => removeBand(t.band)} className="transition-colors"
                            style={{ color: 'var(--color-text-muted)' }}
                            onMouseEnter={(e) => (e.currentTarget.style.color = '#f87171')}
                            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-text-muted)')}>
                      <X size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-2 pt-3" style={{ borderTop: '1px solid var(--color-border)' }}>
          <input
            type="number"
            placeholder="Band number (e.g. 1, 3, 5, 7, 8, 78)"
            value={newBand}
            onChange={(e) => setNewBand(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addBand()}
            className={numInputCls + ' w-52'}
          />
          <button
            onClick={addBand}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm transition-colors"
            style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)', background: 'var(--color-surface2)' }}
          >
            <Plus size={13} />Add Band
          </button>
        </div>
      </Card>

      <Card title="Quality Degradation Ratios">
        <p className="text-xs -mt-1" style={{ color: 'var(--color-text-muted)' }}>
          Set the bitrate ratio for each quality step relative to the camera's base bitrate (NORMAL).
        </p>
        <div className="grid grid-cols-2 gap-5">
          <div className="rounded-xl border p-4 space-y-2" style={{ borderColor: '#fca5a5', background: '#fef2f2' }}>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold px-2 py-0.5 rounded-md" style={{ background: '#fee2e2', color: '#dc2626' }}>DEGRADED</span>
              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Applied on overload entry</span>
            </div>
            <div className="flex items-center gap-2">
              <input type="number" min={1} max={99} step={1}
                value={Math.round(local.degradation.degradedRatio * 100)}
                onChange={(e) => setDegradation('degradedRatio', Number(e.target.value))}
                className={numInputCls + ' w-24'} />
              <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>% of NORMAL bitrate</span>
            </div>
            <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>e.g. NORMAL 4096kbps → {Math.round(4096 * local.degradation.degradedRatio)}kbps</p>
          </div>
          <div className="rounded-xl border p-4 space-y-2" style={{ borderColor: '#fcd34d', background: '#fffbeb' }}>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold px-2 py-0.5 rounded-md" style={{ background: '#fef9c3', color: '#ca8a04' }}>STEP_UP</span>
              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Intermediate recovery step</span>
            </div>
            <div className="flex items-center gap-2">
              <input type="number" min={1} max={99} step={1}
                value={Math.round(local.degradation.stepUpRatio * 100)}
                onChange={(e) => setDegradation('stepUpRatio', Number(e.target.value))}
                className={numInputCls + ' w-24'} />
              <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>% of NORMAL bitrate</span>
            </div>
            <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>e.g. NORMAL 4096kbps → {Math.round(4096 * local.degradation.stepUpRatio)}kbps</p>
          </div>
        </div>
        <div className="rounded-lg px-4 py-2 text-xs flex items-center gap-6"
             style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#16a34a' }}>
          <span className="font-semibold">NORMAL</span>
          <span style={{ color: 'var(--color-text-secondary)' }}>Full restore to camera default (uses GetVideoEncoderConfiguration cache)</span>
        </div>
      </Card>

      <Card title="Timing Settings">
        <div className="grid grid-cols-2 gap-4">
          <NumberInput label="Sliding Window (min)"    value={Math.round(local.slidingWindowSeconds / 60)}   onChange={(v) => setLocal((p) => p ? { ...p, slidingWindowSeconds: v * 60 } : p)} />
          <NumberInput label="Recovery Cooldown (min)" value={Math.round(local.recoveryCooldownSeconds / 60)} onChange={(v) => setLocal((p) => p ? { ...p, recoveryCooldownSeconds: v * 60 } : p)} />
          <NumberInput label="Step Interval (min)"     value={Math.round(local.stepUpIntervalSeconds / 60)}  onChange={(v) => setLocal((p) => p ? { ...p, stepUpIntervalSeconds: v * 60 } : p)} />
          <NumberInput label="Max ONVIF Retries"       value={local.maxOnvifRetries}                          onChange={(v) => setLocal((p) => p ? { ...p, maxOnvifRetries: v } : p)} />
        </div>
      </Card>
    </div>
  )
}

const numInputCls = 'rounded-lg px-3 py-1.5 text-sm w-full focus:outline-none focus:ring-1 focus:ring-indigo-500'
  + ' bg-[var(--color-surface2)] border border-[var(--color-border)] text-[var(--color-text-primary)]'

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl p-5 space-y-4"
         style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
      <h2 className="text-sm font-bold" style={{ color: '#0f172a' }}>{title}</h2>
      {children}
    </div>
  )
}

function NumberInput({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="text-xs font-medium block mb-1" style={{ color: 'var(--color-text-muted)' }}>{label}</label>
      <input type="number" value={value} onChange={(e) => onChange(Number(e.target.value))} className={numInputCls} />
    </div>
  )
}
