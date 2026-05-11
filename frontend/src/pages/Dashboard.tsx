import { useEffect, useState, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, TrendingDown, Clock, WifiOff, ChevronDown, ChevronUp, ChevronLeft, ChevronRight } from 'lucide-react'
import { useCellStore } from '@/store/cellStore'
import { useDeviceStore } from '@/store/deviceStore'
import { fetchCells } from '@/api/cells'
import { fetchDevices } from '@/api/devices'
import { fetchConfig } from '@/api/config'
import { CellStatusPanel } from '@/components/cells/CellStatusPanel'
import { ULRBUsageChart } from '@/components/cells/ULRBUsageChart'
import { CellStateDonut } from '@/components/cells/CellStateDonut'
import { DeviceStatusPanel } from '@/components/devices/DeviceStatusPanel'
import { Sparkline } from '@/components/common/Sparkline'
import { AlertFeed } from '@/components/alerts/AlertFeed'

const PAGE_SIZE = 6

// 스파크라인 히스토리 (최근 20포인트)
const sparkHistory: Record<string, number[]> = {
  overload: [],
  degraded: [],
  recovery: [],
  unmanaged: [],
}
const MAX_SPARK = 20

export function Dashboard() {
  const { cells, setAll: setCells } = useCellStore()
  const { devices, setAll: setDevices } = useDeviceStore()
  const [cellsOpen, setCellsOpen] = useState(true)
  const [devicePage, setDevicePage] = useState(0)

  const { data: cellList }   = useQuery({ queryKey: ['cells'],   queryFn: fetchCells,   refetchInterval: 5000 })
  const { data: deviceList } = useQuery({ queryKey: ['devices'], queryFn: fetchDevices, refetchInterval: 5000 })
  const { data: config }     = useQuery({ queryKey: ['config'],  queryFn: fetchConfig })

  useEffect(() => { if (cellList)   setCells(cellList) },   [cellList,   setCells])
  useEffect(() => { if (deviceList) setDevices(deviceList) }, [deviceList, setDevices])

  const cellArr   = Array.from(cells.values()).sort((a, b) => b.ulRbSum - a.ulRbSum)
  const deviceArr = Array.from(devices.values())

  const overloadEnter        = config?.thresholds[0]?.overloadEnter ?? 30000
  const slidingWindowSeconds = config?.slidingWindowSeconds ?? 60

  const overloadCount  = cellArr.filter((c) => c.state === 'OVERLOAD').length
  const degradedCount  = deviceArr.filter((d) => d.state === 'DEGRADED').length
  const recoveryCount  = deviceArr.filter((d) => d.state === 'RECOVERY_PENDING').length
  const unmanagedCount = deviceArr.filter((d) => d.state === 'UNMANAGED').length
  const managedDeviceArr = deviceArr.filter((d) => d.state !== 'UNMANAGED')

  // 스파크라인 데이터 누적
  const prevRef = useRef({ overloadCount, degradedCount, recoveryCount, unmanagedCount })
  useEffect(() => {
    const p = prevRef.current
    if (p.overloadCount !== overloadCount || p.degradedCount !== degradedCount) {
      sparkHistory.overload.push(overloadCount)
      sparkHistory.degraded.push(degradedCount)
      sparkHistory.recovery.push(recoveryCount)
      sparkHistory.unmanaged.push(unmanagedCount)
      if (sparkHistory.overload.length > MAX_SPARK) sparkHistory.overload.shift()
      if (sparkHistory.degraded.length > MAX_SPARK) sparkHistory.degraded.shift()
      if (sparkHistory.recovery.length > MAX_SPARK) sparkHistory.recovery.shift()
      if (sparkHistory.unmanaged.length > MAX_SPARK) sparkHistory.unmanaged.shift()
      prevRef.current = { overloadCount, degradedCount, recoveryCount, unmanagedCount }
    }
  }, [overloadCount, degradedCount, recoveryCount, unmanagedCount])

  const totalDevicePages = Math.ceil(managedDeviceArr.length / PAGE_SIZE)
  const pagedDevices = managedDeviceArr.slice(devicePage * PAGE_SIZE, (devicePage + 1) * PAGE_SIZE)

  return (
    <div className="p-4 flex gap-4 w-full min-h-0">

      <div className="flex-1 min-w-0 space-y-4">

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <SummaryCard
          label="Overload Cells" value={overloadCount}
          Icon={AlertTriangle} accent="#dc2626" borderColor="#ef4444"
          spark={[...sparkHistory.overload, overloadCount]}
        />
        <SummaryCard
          label="Degraded Devices" value={degradedCount}
          Icon={TrendingDown} accent="#ea580c" borderColor="#f97316"
          spark={[...sparkHistory.degraded, degradedCount]}
        />
        <SummaryCard
          label="Recovery Pending" value={recoveryCount}
          Icon={Clock} accent="#7c3aed" borderColor="#8b5cf6"
          spark={[...sparkHistory.recovery, recoveryCount]}
        />
        <SummaryCard
          label="Unmanaged Devices" value={unmanagedCount}
          Icon={WifiOff} accent="#ca8a04" borderColor="#eab308"
          spark={[...sparkHistory.unmanaged, unmanagedCount]}
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-3 items-stretch">
        <div className="lg:col-span-3 flex flex-col">
          <ULRBUsageChart cells={cellArr} />
        </div>
        <div className="lg:col-span-2 flex flex-col">
          <CellStateDonut cells={cellArr} />
        </div>
      </div>

      {/* 셀 상태 */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-bold"
              style={{ color: '#0f172a' }}>
            Cell Status ({cellArr.length})
          </h2>
          <button
            onClick={() => setCellsOpen((v) => !v)}
            className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg transition-colors"
            style={{ color: 'var(--color-text-secondary)', border: '1px solid var(--color-border)', background: 'var(--color-surface)' }}
          >
            {cellsOpen ? <><ChevronUp size={12} />Collapse</> : <><ChevronDown size={12} />Expand</>}
          </button>
        </div>
        {cellsOpen && (
          <div className="grid grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-2">
            {cellArr.length === 0 && (
              <div className="col-span-5 text-center py-8 rounded-xl text-sm"
                   style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)', border: '1px solid var(--color-border)' }}>
                No cell data received
              </div>
            )}
            {cellArr.map((cell) => (
              <CellStatusPanel
                key={`${cell.groupingKey.ecgi}:${cell.groupingKey.band}`}
                cell={cell}
                overloadEnter={overloadEnter}
                slidingWindowSeconds={slidingWindowSeconds}
              />
            ))}
          </div>
        )}
      </div>

      {/* 단말 상태 */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-bold"
              style={{ color: '#0f172a' }}>
            Device Status ({managedDeviceArr.length})
          </h2>
          {totalDevicePages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setDevicePage((p) => Math.max(0, p - 1))}
                disabled={devicePage === 0}
                className="w-7 h-7 flex items-center justify-center rounded-lg transition-colors disabled:opacity-40"
                style={{ border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text-secondary)' }}
              >
                <ChevronLeft size={13} />
              </button>
              <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                {devicePage + 1} / {totalDevicePages}
              </span>
              <button
                onClick={() => setDevicePage((p) => Math.min(totalDevicePages - 1, p + 1))}
                disabled={devicePage >= totalDevicePages - 1}
                className="w-7 h-7 flex items-center justify-center rounded-lg transition-colors disabled:opacity-40"
                style={{ border: '1px solid var(--color-border)', background: 'var(--color-surface)', color: 'var(--color-text-secondary)' }}
              >
                <ChevronRight size={13} />
              </button>
            </div>
          )}
        </div>
        <div className="grid grid-cols-3 xl:grid-cols-4 gap-2">
          {managedDeviceArr.length === 0 && (
            <div className="col-span-4 text-center py-8 rounded-xl text-sm"
                 style={{ background: 'var(--color-surface)', color: 'var(--color-text-muted)', border: '1px solid var(--color-border)' }}>
              No device data received
            </div>
          )}
          {pagedDevices.map((device) => (
            <DeviceStatusPanel key={device.routerCtn} device={device} />
          ))}
        </div>
      </div>

      </div>{/* end main flex-1 */}

      {/* Alert feed right sidebar */}
      <div className="w-72 shrink-0 self-start sticky top-4"
           style={{ height: 'calc(100vh - 5rem)' }}>
        <div className="rounded-xl overflow-hidden flex flex-col h-full"
             style={{ background: '#ffffff', border: '1px solid #e2e8f0' }}>
          <AlertFeed />
        </div>
      </div>

    </div>
  )
}

interface SummaryCardProps {
  label: string
  value: number
  Icon: React.ElementType
  accent: string
  borderColor: string
  spark: number[]
}

function SummaryCard({ label, value, Icon, accent, borderColor, spark }: SummaryCardProps) {
  return (
    <div className="rounded-xl p-3 flex items-center gap-3 relative overflow-hidden"
         style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderLeft: `4px solid ${borderColor}`, boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
      <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
           style={{ background: `${accent}15` }}>
        <Icon size={18} style={{ color: accent }} strokeWidth={2} />
      </div>
      <div className="flex-1 min-w-0 flex flex-col items-end text-right">
        <div className="text-3xl font-bold leading-none" style={{ color: accent }}>{value}</div>
        <div className="text-sm font-semibold mt-1 truncate" style={{ color: '#94a3b8' }}>{label}</div>
      </div>
      {spark.length > 1 && (
        <div className="w-16 shrink-0">
          <Sparkline data={spark} color={accent} />
        </div>
      )}
    </div>
  )
}
