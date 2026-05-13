import { useEffect, useRef } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { format } from 'date-fns'
import type { CellStatus } from '@/types'

interface DataPoint { ts: number; value: number; key: string }

const MAX_POINTS = 60
const history = new Map<string, DataPoint[]>()
const keyOf = (c: CellStatus) => `${c.groupingKey.ecgi}:${c.groupingKey.band}`

export function ULRBUsageChart({ cells }: { cells: CellStatus[] }) {
  const nowRef = useRef(Date.now())

  useEffect(() => {
    const now = Date.now()
    nowRef.current = now
    cells.forEach((c) => {
      const k = keyOf(c)
      if (!history.has(k)) history.set(k, [])
      const pts = history.get(k)!
      pts.push({ ts: now, value: c.ulRbSum, key: k })
      if (pts.length > MAX_POINTS) pts.splice(0, pts.length - MAX_POINTS)
    })
  }, [cells])

  const merged = new Map<number, number>()
  history.forEach((pts) => pts.forEach((p) => merged.set(p.ts, (merged.get(p.ts) ?? 0) + p.value)))
  const data = Array.from(merged.entries())
    .sort(([a], [b]) => a - b)
    .map(([ts, value]) => ({ time: format(ts, 'HH:mm:ss'), value }))

  return (
    <div className="rounded-xl p-4 flex flex-col flex-1"
         style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
      <h3 className="text-sm font-bold mb-4"
          style={{ color: '#0f172a' }}>
        UL_RB Usage Trend (All Cells)
      </h3>
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="ulrbGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#2563eb" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="time"
            tick={{ fontSize: 10, fill: '#94a3b8' }}
            interval="preserveStartEnd"
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 10, fill: '#94a3b8' }}
            width={44}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              borderRadius: '8px',
              border: '1px solid #e2e8f0',
              background: '#ffffff',
              fontSize: 12,
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
            }}
            labelStyle={{ color: '#64748b' }}
            itemStyle={{ color: '#2563eb' }}
            formatter={((v: unknown) => [(v as number).toLocaleString(), 'UL_RB_Usage']) as never}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="#2563eb"
            fill="url(#ulrbGrad)"
            strokeWidth={2}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
