interface Props {
  status: 'connecting' | 'connected' | 'disconnected'
}

const config = {
  connecting: { dot: 'bg-yellow-400 animate-pulse', label: '연결 중…' },
  connected: { dot: 'bg-green-500', label: '연결됨' },
  disconnected: { dot: 'bg-red-500', label: '연결 끊김' },
}

export function ConnectionStatus({ status }: Props) {
  const { dot, label } = config[status]
  return (
    <div className="flex items-center gap-1.5 text-sm text-slate-600">
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      {label}
    </div>
  )
}
