import { useState, useRef, useCallback, useEffect } from 'react'

export function useWebSocket(url, { onMessage, autoConnect = false } = {}) {
  const [status, setStatus] = useState('disconnected')
  const wsRef = useRef(null)
  const retriesRef = useRef(0)
  const reconnectTimerRef = useRef(null)
  const onMessageRef = useRef(onMessage)
  const maxRetries = 5

  // Keep onMessage ref current without triggering reconnects
  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  const connect = useCallback(() => {
    const wsUrl = url.startsWith('ws')
      ? url
      : `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}${url}`

    setStatus('connecting')
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('connected')
      retriesRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data)
        onMessageRef.current?.(parsed)
      } catch {
        // Ignore unparseable frames
      }
    }

    ws.onclose = () => {
      setStatus('disconnected')
      if (retriesRef.current < maxRetries) {
        const delay = Math.min(1000 * Math.pow(2, retriesRef.current), 30000)
        retriesRef.current += 1
        reconnectTimerRef.current = setTimeout(() => {
          connect()
        }, delay)
      }
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [url])

  const sendMessage = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  const disconnect = useCallback(() => {
    retriesRef.current = maxRetries // prevent reconnect
    clearTimeout(reconnectTimerRef.current)
    wsRef.current?.close()
  }, [])

  useEffect(() => {
    if (autoConnect) {
      connect()
    }
    return () => {
      disconnect()
    }
  }, [autoConnect, connect, disconnect])

  return { status, connect, sendMessage, disconnect }
}
