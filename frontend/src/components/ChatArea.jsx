import { useRef, useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowUp, Plus, AlertCircle, Mic } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import MessageBubble from './MessageBubble'
import ActionViewer from './ActionViewer'
import VoiceButton from './VoiceButton'

export default function ChatArea({
  messages = [],
  actions = [],
  isLoading = false,
  streamingText = '',
  error = null,
  onSendMessage,
  onClear,
  voice = {},
}) {
  const { t } = useTranslation()
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText, actions])

  const handleInputChange = useCallback((e) => {
    const el = e.target
    setInput(el.value)
    el.style.height = 'auto'
    const maxHeight = 28 * 6
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
  }, [])

  const handleSend = useCallback(() => {
    const trimmed = input.trim()
    if (!trimmed || isLoading) return
    onSendMessage(trimmed)
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [input, isLoading, onSendMessage])

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend]
  )

  const canSend = input.trim().length > 0 && !isLoading
  const showStreaming = streamingText.length > 0
  const showActions = actions.length > 0 || (isLoading && !showStreaming)
  const isEmpty = messages.length === 0 && !showStreaming && !showActions

  /* Shared input bar — centered, max 768px like ChatGPT */
  const inputBar = (
    <div style={{ width: '100%', maxWidth: 768, margin: '0 auto', padding: '0 16px' }}>
      {/* Voice transcript preview */}
      {voice.isListening && voice.transcript && (
        <div className="voice-transcript mb-2">
          <Mic size={14} style={{ color: '#ef4444', flexShrink: 0 }} />
          <span>{voice.transcript}</span>
        </div>
      )}

      <div
        className="chat-input-wrapper"
        onFocus={(e) => {
          e.currentTarget.style.borderColor = '#555'
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = 'var(--border)'
        }}
      >
        <button className="attach-btn" aria-label="Attach">
          <Plus size={20} />
        </button>

        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={t('chat.placeholder')}
          rows={1}
          disabled={isLoading}
          className="chat-textarea"
        />

        <VoiceButton
          isListening={voice.isListening}
          isSpeaking={voice.isSpeaking}
          supported={voice.sttSupported}
          onToggle={voice.toggleListening}
          onStopTTS={voice.stopSpeaking}
        />

        <AnimatePresence>
          {canSend && (
            <motion.button
              key="send"
              initial={{ opacity: 0, scale: 0.7 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.7 }}
              transition={{ duration: 0.15 }}
              onClick={handleSend}
              className="send-btn"
              whileTap={{ scale: 0.9 }}
              aria-label={t('chat.send')}
            >
              <ArrowUp size={20} strokeWidth={2.5} />
            </motion.button>
          )}

          {isLoading && (
            <motion.span
              key="spinner"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              style={{
                flexShrink: 0,
                width: 36,
                height: 36,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <motion.span
                style={{
                  display: 'block',
                  width: 20,
                  height: 20,
                  borderRadius: '50%',
                  border: '2px solid var(--text-muted)',
                  borderTopColor: 'transparent',
                }}
                animate={{ rotate: 360 }}
                transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
              />
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      <p
        className="text-center mt-2 pb-1"
        style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}
      >
        JARVIS can make mistakes. Consider checking important info.
      </p>
    </div>
  )

  /* Empty state — greeting centered with input */
  if (isEmpty) {
    return (
      <div className="chat-area">
        <div
          className="d-flex flex-column align-items-center justify-content-center"
          style={{ flex: 1, padding: '0 16px' }}
        >
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
            className="d-flex flex-column align-items-center w-100"
          >
            <h1
              className="fw-medium mb-4"
              style={{ color: 'var(--text-primary)', fontSize: '1.5rem' }}
            >
              What&apos;s on the agenda today?
            </h1>

            <div className="w-100 d-flex justify-content-center">
              {inputBar}
            </div>
          </motion.div>
        </div>
      </div>
    )
  }

  /* Chat state — messages scrollable, input at bottom */
  return (
    <div className="chat-area">
      {/* Messages — full width scroll */}
      <div className="messages-scroll">
        <AnimatePresence initial={false}>
          {messages.map((msg, idx) => (
            <MessageBubble key={idx} message={msg} isStreaming={false} />
          ))}
        </AnimatePresence>

        <AnimatePresence>
          {showActions && (
            <div
              key="actions"
              className="w-100 px-4 py-3"
            >
              <ActionViewer
                actions={actions}
                isLoading={isLoading && !showStreaming}
              />
            </div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {showStreaming && (
            <MessageBubble
              key="streaming"
              message={{ role: 'assistant', content: streamingText }}
              isStreaming
            />
          )}
        </AnimatePresence>

        <AnimatePresence>
          {error && (
            <motion.div
              key="error"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.2 }}
              className="w-100 px-4 my-3"
            >
              <div className="error-alert">
                <AlertCircle
                  size={16}
                  style={{ flexShrink: 0, marginTop: 2, color: 'var(--error)' }}
                />
                <p style={{ margin: 0 }}>{error}</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div ref={bottomRef} style={{ height: 16 }} />
      </div>

      {/* Input area — bottom */}
      <div className="chat-input-area">
        <div className="d-flex justify-content-center w-100">
          {inputBar}
        </div>
      </div>
    </div>
  )
}
