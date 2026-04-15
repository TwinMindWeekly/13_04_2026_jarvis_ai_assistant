import { useState, useCallback, useRef } from 'react'
import { agentAPI } from '../services/api'
import { useWebSocket } from './useWebSocket'

const RETRY_DELAYS_MS = [250, 500, 1000]

const isRetryableError = (err) => {
  // Network errors (no response) → retry. HTTP 4xx/5xx with response → don't retry.
  if (!err) return false
  if (err.code === 'ERR_NETWORK' || err.code === 'ECONNABORTED') return true
  return !err.response
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export function useAgent(provider, model) {
  const [messages, setMessages] = useState([])
  const [actions, setActions] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [streamingText, setStreamingText] = useState('')
  const conversationIdRef = useRef(null)
  const streamingTextRef = useRef('')

  const handleWsMessage = useCallback((event) => {
    if (event.type === 'text') {
      streamingTextRef.current = streamingTextRef.current + event.content
      setStreamingText(streamingTextRef.current)
    }

    if (event.type === 'action') {
      setActions((prev) => [...prev, { ...event, status: 'running' }])
    }

    if (event.type === 'action_result') {
      setActions((prev) =>
        prev.map((a) =>
          a.tool === event.tool && a.status === 'running'
            ? { ...a, ...event, status: 'completed' }
            : a
        )
      )
    }

    if (event.type === 'done') {
      const finalText = streamingTextRef.current
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: finalText },
      ])
      streamingTextRef.current = ''
      setStreamingText('')
      setActions([])
      setIsLoading(false)
    }
  }, [])

  const { status: wsStatus, connect, sendMessage: wsSend, disconnect } =
    useWebSocket('/ws/agent', { onMessage: handleWsMessage })

  const sendMessage = useCallback(
    async (text) => {
      // 1. Append user message ONCE — outside retry loop (idempotent UX).
      const userMsg = { role: 'user', content: text }
      setMessages((prev) => [...prev, userMsg])
      setIsLoading(true)
      setError(null)
      setActions([])
      setStreamingText('')
      streamingTextRef.current = ''

      // 2. WebSocket path — single send, server pushes events back.
      if (wsStatus === 'connected') {
        try {
          wsSend({ message: text, provider, model })
          return
        } catch (err) {
          // Fall through to REST fallback
        }
      }

      // 3. REST fallback with retry on transient network errors.
      let lastErr = null
      for (let attempt = 0; attempt <= RETRY_DELAYS_MS.length; attempt++) {
        try {
          const { data } = await agentAPI.execute(
            text,
            provider,
            model,
            conversationIdRef.current
          )
          conversationIdRef.current = data.conversation_id
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: data.response,
              actions: data.actions,
            },
          ])
          setIsLoading(false)
          return
        } catch (err) {
          lastErr = err
          if (attempt < RETRY_DELAYS_MS.length && isRetryableError(err)) {
            await sleep(RETRY_DELAYS_MS[attempt])
            continue
          }
          break
        }
      }

      const message =
        lastErr?.response?.data?.detail ||
        (isRetryableError(lastErr)
          ? 'Cannot reach backend. Please check the server is running.'
          : lastErr?.message || 'Something went wrong')
      setError(message)
      setIsLoading(false)
    },
    [provider, model, wsStatus, wsSend]
  )

  const clearMessages = useCallback(() => {
    setMessages([])
    setActions([])
    setStreamingText('')
    streamingTextRef.current = ''
    conversationIdRef.current = null
    setError(null)
  }, [])

  const dismissError = useCallback(() => setError(null), [])

  return {
    messages,
    actions,
    isLoading,
    error,
    streamingText,
    sendMessage,
    clearMessages,
    dismissError,
    wsStatus,
    connect,
    disconnect,
  }
}
