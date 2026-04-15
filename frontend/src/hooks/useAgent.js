import { useState, useCallback, useRef } from 'react'
import { agentAPI } from '../services/api'
import { useWebSocket } from './useWebSocket'

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
      const userMsg = { role: 'user', content: text }
      setMessages((prev) => [...prev, userMsg])
      setIsLoading(true)
      setError(null)
      setActions([])
      setStreamingText('')
      streamingTextRef.current = ''

      try {
        if (wsStatus === 'connected') {
          wsSend({ message: text, provider, model })
        } else {
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
        }
      } catch (err) {
        setError(
          err.response?.data?.detail || err.message || 'Something went wrong'
        )
        setIsLoading(false)
      }
    },
    [provider, model, wsStatus, wsSend]
  )

  const clearMessages = useCallback(() => {
    setMessages([])
    setActions([])
    setStreamingText('')
    streamingTextRef.current = ''
    conversationIdRef.current = null
  }, [])

  return {
    messages,
    actions,
    isLoading,
    error,
    streamingText,
    sendMessage,
    clearMessages,
    wsStatus,
    connect,
    disconnect,
  }
}
