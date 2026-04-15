import { useRef, useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowUp, Plus, AlertCircle, Zap } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import MessageBubble from './MessageBubble'
import ActionViewer from './ActionViewer'

export default function ChatArea({
  messages = [],
  actions = [],
  isLoading = false,
  streamingText = '',
  error = null,
  onSendMessage,
  onClear,
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

  /* Shared input bar component */
  const inputBar = (
    <div className="w-full max-w-3xl mx-auto px-4">
      <div
        className="flex items-end gap-3 px-4 py-3 rounded-3xl transition-colors duration-150"
        style={{
          background: 'var(--bg-input)',
          border: '1px solid var(--border)',
        }}
        onFocusCapture={(e) => {
          e.currentTarget.style.borderColor = '#555'
        }}
        onBlurCapture={(e) => {
          e.currentTarget.style.borderColor = 'var(--border)'
        }}
      >
        {/* Plus button */}
        <button
          className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-colors"
          style={{ color: 'var(--text-secondary)' }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.08)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent'
          }}
          aria-label="Attach"
        >
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
          className="flex-1 bg-transparent resize-none text-base outline-none leading-7 disabled:opacity-50"
          style={{
            color: 'var(--text-primary)',
            minHeight: '28px',
            maxHeight: '168px',
            overflowY: 'auto',
            caretColor: 'var(--text-primary)',
          }}
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
              className="flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center"
              style={{
                background: 'var(--text-primary)',
                color: 'var(--bg-main)',
              }}
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
              className="flex-shrink-0 w-9 h-9 flex items-center justify-center"
            >
              <motion.span
                className="w-5 h-5 rounded-full border-2"
                style={{ display: 'block', borderColor: 'var(--text-muted)', borderTopColor: 'transparent' }}
                animate={{ rotate: 360 }}
                transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
              />
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      <p
        className="text-center text-xs mt-2.5 pb-1"
        style={{ color: 'var(--text-muted)' }}
      >
        JARVIS can make mistakes. Consider checking important info.
      </p>
    </div>
  )

  /* Empty state — greeting centered with input in the middle */
  if (isEmpty) {
    return (
      <div
        className="flex flex-col h-full"
        style={{ background: 'var(--bg-main)' }}
      >
        <div className="flex-1 flex flex-col items-center justify-center px-4">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
            className="flex flex-col items-center w-full"
          >
            <h1
              className="text-2xl font-medium mb-8"
              style={{ color: 'var(--text-primary)' }}
            >
              What's on the agenda today?
            </h1>

            {inputBar}
          </motion.div>
        </div>
      </div>
    )
  }

  /* Chat state — messages scrollable, input at bottom */
  return (
    <div
      className="flex flex-col h-full overflow-hidden"
      style={{ background: 'var(--bg-main)' }}
    >
      {/* Message list */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto flex flex-col">
          <AnimatePresence initial={false}>
            {messages.map((msg, idx) => (
              <MessageBubble key={idx} message={msg} isStreaming={false} />
            ))}
          </AnimatePresence>

          <AnimatePresence>
            {showActions && (
              <div key="actions" className="px-4 py-3">
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
                className="flex items-start gap-3 mx-4 my-3 px-4 py-3 rounded-xl"
                style={{
                  background: 'rgba(239,68,68,0.08)',
                  border: '1px solid rgba(239,68,68,0.25)',
                }}
              >
                <AlertCircle
                  size={16}
                  className="flex-shrink-0 mt-0.5"
                  style={{ color: 'var(--error)' }}
                />
                <p className="text-sm" style={{ color: '#fca5a5' }}>
                  {error}
                </p>
              </motion.div>
            )}
          </AnimatePresence>

          <div ref={bottomRef} className="h-4" />
        </div>
      </div>

      {/* Input area — bottom */}
      <div
        className="flex-shrink-0 pb-4 pt-2"
        style={{ background: 'var(--bg-main)' }}
      >
        {inputBar}
      </div>
    </div>
  )
}
