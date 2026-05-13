import { useState, useRef, useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { LayoutDashboard, History, Camera, Settings, Bell } from 'lucide-react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useAlertStore } from '@/store/alertStore'
import { AlertFeed } from '@/components/alerts/AlertFeed'

const WS_URL =
  import.meta.env.VITE_WS_URL ??
  `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/events`

const NAV_ITEMS = [
  { to: '/',        label: 'Dashboard',      Icon: LayoutDashboard },
  { to: '/history', label: 'History',        Icon: History },
  { to: '/cameras', label: 'Camera Mgmt',    Icon: Camera },
  { to: '/config',  label: 'Configuration',  Icon: Settings },
]

const PAGE_TITLES: Record<string, string> = {
  '/':        'Dashboard',
  '/history': 'History',
  '/cameras': 'Camera Management',
  '/config':  'Configuration',
}

function AlertBell() {
  const { alerts } = useAlertStore()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const unread = alerts.length

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative w-9 h-9 flex items-center justify-center rounded-lg transition-colors"
        style={{ color: open ? '#2563eb' : '#64748b', background: open ? '#eff6ff' : 'transparent' }}
      >
        <Bell size={17} />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 flex items-center justify-center rounded-full text-[10px] font-bold text-white px-1"
                style={{ background: '#ef4444' }}>
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 rounded-2xl overflow-hidden flex flex-col z-50"
          style={{ width: 380, maxHeight: 520, background: '#fff', border: '1px solid #e2e8f0', boxShadow: '0 8px 30px rgba(0,0,0,0.12)' }}
        >
          <AlertFeed />
        </div>
      )}
    </div>
  )
}

export function Layout() {
  const status = useWebSocket(WS_URL)
  const location = useLocation()
  const title = PAGE_TITLES[location.pathname] ?? '대시보드'

  const wsIndicator: Record<string, string> = {
    connected:    '#22c55e',
    connecting:   '#f59e0b',
    disconnected: '#ef4444',
  }

  return (
    <div className="flex h-screen" style={{ background: 'var(--color-bg)' }}>
      {/* Sidebar */}
      <aside className="w-14 flex flex-col shrink-0 z-10"
             style={{ background: '#ffffff', borderRight: '1px solid #e2e8f0' }}>
        {/* Logo */}
        <div className="h-14 flex items-center justify-center"
             style={{ borderBottom: '1px solid #e2e8f0' }}>
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
               style={{ background: 'linear-gradient(135deg, #2563eb, #06b6d4)' }}>
            <span className="text-white text-xs font-bold leading-none">CT</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 flex flex-col items-center py-3 gap-1">
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              title={label}
              className="relative group w-10 h-10 flex items-center justify-center rounded-lg transition-all duration-150"
              style={({ isActive }) => isActive
                ? { background: '#2563eb', color: '#ffffff', boxShadow: '0 2px 8px #2563eb44' }
                : { color: '#94a3b8' }}
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute -left-[3px] top-2 bottom-2 w-[3px] rounded-r-full"
                          style={{ background: '#2563eb' }} />
                  )}
                  <Icon size={18} strokeWidth={isActive ? 2.2 : 1.8} />
                  <span className="pointer-events-none absolute left-full ml-2.5 px-2 py-1 rounded-lg text-xs font-medium whitespace-nowrap
                                   opacity-0 group-hover:opacity-100 transition-opacity duration-150 shadow-lg z-50"
                        style={{ background: '#1e293b', color: '#f1f5f9' }}>
                    {label}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* WS status dot */}
        <div className="h-14 flex items-center justify-center"
             style={{ borderTop: '1px solid #e2e8f0' }}
             title={status}>
          <span className="w-2 h-2 rounded-full" style={{ background: wsIndicator[status] ?? '#94a3b8' }} />
        </div>
      </aside>

      {/* Content area with header */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top header */}
        <header className="h-14 shrink-0 flex items-center justify-between px-6 z-20"
                style={{ background: '#ffffff', borderBottom: '1px solid #e2e8f0' }}>
          <span className="text-xl font-bold" style={{ color: '#0f172a' }}>{title}</span>
          <AlertBell />
        </header>

        <main className="flex-1 overflow-y-auto h-full">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
