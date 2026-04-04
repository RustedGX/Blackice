import { useEffect, useRef, useCallback } from 'react'
import { usePortfolioStore, useMarketStore, useSignalStore, useWSStore } from '../store'

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const setConnected = useWSStore((s) => s.setConnected)
  const updatePrices = useMarketStore((s) => s.updatePrices)
  const updateBalances = usePortfolioStore((s) => s.updateBalances)
  const addSignal = useSignalStore((s) => s.addSignal)

  const connect = useCallback(() => {
    const clientId = `web-${Date.now()}`
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/${clientId}`)

    ws.onopen = () => {
      setConnected(true)
      // Start ping
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        } else {
          clearInterval(ping)
        }
      }, 30000)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        switch (msg.type) {
          case 'price_update':
            updatePrices(msg.data)
            break
          case 'portfolio_update':
            updateBalances(msg.data.cash_balance, msg.data.total_value)
            break
          case 'signal':
            addSignal(msg.data)
            break
          default:
            break
        }
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = () => {
      setConnected(false)
      // Reconnect after 3 seconds
      reconnectTimer.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [setConnected, updatePrices, updateBalances, addSignal])

  useEffect(() => {
    connect()
    return () => {
      reconnectTimer.current && clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])
}
