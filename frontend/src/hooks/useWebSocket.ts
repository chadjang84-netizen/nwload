import { useEffect, useRef, useState } from 'react'
import type { WSEvent } from '@/types'
import { useCellStore } from '@/store/cellStore'
import { useDeviceStore } from '@/store/deviceStore'
import { useAlertStore } from '@/store/alertStore'

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected'

export function useWebSocket(url: string) {
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryDelay = useRef(1000)

  const setCellStatus = useCellStore((s) => s.setStatus)
  const setDeviceStatus = useDeviceStore((s) => s.setStatus)
  const addAlert = useAlertStore((s) => s.addAlert)

  useEffect(() => {
    let active = true

    const connect = () => {
      if (!active) return
      setStatus('connecting')
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (!active) return
        setStatus('connected')
        retryDelay.current = 1000
      }

      ws.onmessage = (ev) => {
        try {
          const msg: WSEvent = JSON.parse(ev.data)
          if (msg.type === 'cell_state_changed') setCellStatus(msg.data)
          else if (msg.type === 'device_state_changed') setDeviceStatus(msg.data)
          else if (msg.type === 'alert') addAlert(msg.data)
        } catch {
          // ignore malformed messages
        }
      }

      ws.onclose = () => {
        if (!active) return
        setStatus('disconnected')
        // exponential backoff, cap at 30s
        retryRef.current = setTimeout(() => {
          retryDelay.current = Math.min(retryDelay.current * 2, 30000)
          connect()
        }, retryDelay.current)
      }

      ws.onerror = () => ws.close()
    }

    connect()

    return () => {
      active = false
      if (retryRef.current) clearTimeout(retryRef.current)
      wsRef.current?.close()
    }
  }, [url, setCellStatus, setDeviceStatus, addAlert])

  return status
}
