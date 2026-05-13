import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import type { CellStatus } from '@/types'

const COLORS: Record<string, string> = {
  NORMAL:     '#16a34a',
  WARNING:    '#ca8a04',
  CONGESTION: '#ea580c',
  OVERLOAD:   '#dc2626',
}

const LABELS: Record<string, string> = {
  NORMAL: 'Normal', WARNING: 'Warning', CONGESTION: 'Congestion', OVERLOAD: 'Overload',
}

interface Props {
  cells: CellStatus[]
}

export function CellStateDonut({ cells }: Props) {
  const counts: Record<string, number> = { NORMAL: 0, WARNING: 0, CONGESTION: 0, OVERLOAD: 0 }
  cells.forEach((c) => { if (counts[c.state] !== undefined) counts[c.state]++ })

  const data = Object.entries(counts)
    .filter(([, v]) => v > 0)
    .map(([state, value]) => ({ state, value, label: LABELS[state] }))

  const total = cells.length

  return (
    <div className="rounded-xl p-4 flex flex-col flex-1 justify-center"
         style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
      <h3 className="text-sm font-bold mb-3"
          style={{ color: '#0f172a' }}>
        Cell State Distribution
      </h3>

      {total === 0 ? (
        <div className="flex-1 flex items-center justify-center text-sm" style={{ color: 'var(--color-text-muted)', minHeight: 140 }}>
          No data
        </div>
      ) : (
        <div className="flex items-center gap-4">
          <div className="relative shrink-0" style={{ width: 140, height: 140 }}>
            <ResponsiveContainer width={140} height={140}>
              <PieChart>
                <Pie
                  data={data}
                  cx={65}
                  cy={65}
                  innerRadius={42}
                  outerRadius={62}
                  dataKey="value"
                  strokeWidth={0}
                  isAnimationActive={false}
                >
                  {data.map((entry) => (
                    <Cell key={entry.state} fill={COLORS[entry.state] ?? '#94a3b8'} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', fontSize: 12 }}
                  formatter={((v: unknown, _: unknown, props: { payload?: { label?: string } }) => [v as number, props.payload?.label ?? '']) as never}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>{total}</span>
              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Cells</span>
            </div>
          </div>

          <div className="flex flex-col gap-2 flex-1">
            {Object.entries(counts).map(([state, count]) => (
              <div key={state} className="flex items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: COLORS[state] }} />
                  <span className="truncate" style={{ color: 'var(--color-text-secondary)' }}>{LABELS[state]}</span>
                </div>
                <span className="font-semibold shrink-0 w-6 text-center" style={{ color: 'var(--color-text-primary)' }}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
