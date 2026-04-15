import { useRef, useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Trash2, AlertCircle } from 'lucide-react'
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

  // Auto-scroll to bottom when messages or streaming text changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText, actions])

  // Auto-grow textarea
  const handleInputChange = useCallback((e) => {
    const el = e.target
    setInput(el.value)
    el.style.height = 'auto'
    const lineHeight = 24
    const maxHeight = lineHeight * 5
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

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto flex flex-col gap-4">
          <AnimatePresence initial={false}>
            {messages.map((msg, idx) => (
              <MessageBubble key={idx} message={msg} isStreaming={false} />
            ))}
          </AnimatePresence>

          {/* Actions viewer appears inline between last user msg and streaming reply */}
          <AnimatePresence>
            {showActions && (
              <ActionViewer
                key="actions"
                actions={actions}
                isLoading={isLoading && !showStreaming}
              />
            )}
          </AnimatePresence>

          {/* Streaming bubble */}
          <AnimatePresence>
            {showStreaming && (
              <MessageBubble
                key="streaming"
                message={{ role: 'assistant', content: streamingText }}
                isStreaming
              />
            )}
          </AnimatePresence>

          {/* Error panel */}
          <AnimatePresence>
            {error && (
              <motion.div
                key="error"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.2 }}
                className="flex items-start gap-3 px-4 py-3 rounded-2xl"
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

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input area */}
      <div
        className="flex-shrink-0 px-4 pb-5 pt-3"
        style={{ borderTop: '1px solid var(--glass-border)' }}
      >
        <div className="max-w-3xl mx-auto">
          <div
            className="flex items-end gap-2 px-4 py-3 rounded-2xl transition-all duration-200"
            style={{
              background: 'var(--glass-bg)',
              border: '1px solid var(--glass-border)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
              boxShadow: 'var(--glass-shadow)',
            }}
            onFocusCapture={(e) => {
              e.currentTarget.style.borderColor = 'rgba(99,102,241,0.45)'
              e.currentTarget.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.08), var(--glass-shadow)'
            }}
            onBlurCapture={(e) => {
              e.currentTarget.style.borderColor = 'var(--glass-border)'
              e.currentTarget.style.boxShadow = 'var(--glass-shadow)'
            }}
          >
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={t('chat.placeholder')}
              rows={1}
              disabled={isLoading}
              className="flex-1 bg-transparent resize-none text-sm outline-none leading-6 placeholder:opacity-40 disabled:opacity-50"
              style={{
                color: 'var(--text-primary)',
                minHeight: '24px',
                maxHeight: '120px',
                overflowY: 'auto',
              }}
            />

            {/* Clear button */}
            {messages.length > 0 && !isLoading && (
              <button
                onClick={onClear}
                className="flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-150"
                style={{ color: 'var(--text-muted)' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(239,68,68,0.1)'
                  e.currentTarget.style.color = 'var(--error)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.color = 'var(--text-muted)'
                }}
                title={t('chat.clear')}
                aria-label={t('chat.clear')}
              >
                <Trash2 size={14} />
              </button>
            )}

            {/* Send button */}
            <motion.button
              onClick={handleSend}
              disabled={!canSend}
              className="flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-150"
              style={{
                background: canSend ? 'var(--accent)' : 'rgba(255,255,255,0.06)',
                color: canSend ? '#fff' : 'var(--text-muted)',
                cursor: canSend ? 'pointer' : 'default',
              }}
              whileTap={canSend ? { scale: 0.9 } : {}}
              aria-label={t('chat.send')}
            >
              {isLoading ? (
                <motion.span
                  className="w-3.5 h-3.5 rounded-full border-2 border-current border-t-transparent"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
                  style={{ display: 'block' }}
                />
              ) : (
                <Send size={14} />
              )}
            </motion.button>
          </div>

          <p
            className="text-center text-[10px] mt-2"
            style={{ color: 'var(--text-muted)' }}
          >
            Enter to send · Shift+Enter for newline
          </p>
        </div>
      </div>
    </div>
  )
}
