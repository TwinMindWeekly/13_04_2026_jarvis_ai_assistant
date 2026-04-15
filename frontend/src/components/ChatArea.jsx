import { useRef, useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowUp, AlertCircle, Zap } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import MessageBubble from './MessageBubble'
import ActionViewer from './ActionViewer'

const SUGGESTION_CHIPS = [
  { icon: '🔍', label: 'Search the web for me' },
  { icon: '💡', label: 'Help me brainstorm ideas' },
  { icon: '📝', label: 'Summarize a document' },
  { icon: '🖥️', label: 'Take a screenshot' },
]

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
    const maxHeight = 24 * 5
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

  const handleChipClick = useCallback(
    (label) => {
      if (isLoading) return
      onSendMessage(label)
    },
    [isLoading, onSendMessage]
  )

  const canSend = input.trim().length > 0 && !isLoading
  const showStreaming = streamingText.length > 0
  const showActions = actions.length > 0 || (isLoading && !showStreaming)
  const isEmpty = messages.length === 0 && !showStreaming && !showActions

  return (
    <div
      className="flex flex-col h-full overflow-hidden"
      style={{ background: 'var(--bg-main)' }}
    >
      {/* Message list */}
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          /* Empty state */
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
            className="flex flex-col items-center justify-center h-full px-4 pb-32"
          >
            <div className="flex flex-col items-center gap-3 mb-8">
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center"
                style={{ background: 'var(--accent)' }}
              >
                <Zap size={28} color="#fff" />
              </div>
              <h1
                className="text-3xl font-bold tracking-tight"
                style={{ color: 'var(--text-primary)' }}
              >
                JARVIS
              </h1>
              <p
                className="text-base"
                style={{ color: 'var(--text-secondary)' }}
              >
                How can I help you today?
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2 w-full max-w-lg">
              {SUGGESTION_CHIPS.map((chip) => (
                <motion.button
                  key={chip.label}
                  onClick={() => handleChipClick(chip.label)}
                  className="flex items-center gap-2.5 px-4 py-3 rounded-xl text-sm text-left transition-colors duration-150"
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-secondary)',
                  }}
                  whileHover={{ borderColor: 'var(--border-light)', color: 'var(--text-primary)' }}
                  whileTap={{ scale: 0.97 }}
                >
                  <span>{chip.icon}</span>
                  <span>{chip.label}</span>
                </motion.button>
              ))}
            </div>
          </motion.div>
        ) : (
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
        )}

        {isEmpty && <div ref={bottomRef} />}
      </div>

      {/* Input area — fixed to bottom of flex column */}
      <div
        className="flex-shrink-0 px-4 pb-4 pt-2"
        style={{ background: 'var(--bg-main)' }}
      >
        <div className="max-w-3xl mx-auto">
          <div
            className="flex items-end gap-2 px-4 py-3 rounded-2xl transition-colors duration-150"
            style={{
              background: 'var(--bg-input)',
              border: '1px solid var(--border)',
            }}
            onFocusCapture={(e) => {
              e.currentTarget.style.borderColor = 'var(--accent)'
            }}
            onBlurCapture={(e) => {
              e.currentTarget.style.borderColor = 'var(--border)'
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
              className="flex-1 bg-transparent resize-none text-base outline-none leading-6 disabled:opacity-50"
              style={{
                color: 'var(--text-primary)',
                minHeight: '28px',
                maxHeight: '120px',
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
                  <ArrowUp size={18} strokeWidth={2.5} />
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
                    className="w-4 h-4 rounded-full border-2"
                    style={{ display: 'block', borderColor: 'var(--text-muted)', borderTopColor: 'transparent' }}
                    animate={{ rotate: 360 }}
                    transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
                  />
                </motion.span>
              )}
            </AnimatePresence>
          </div>

          <p
            className="text-center text-xs mt-2"
            style={{ color: 'var(--text-muted)' }}
          >
            JARVIS can make mistakes. Consider checking important info.
          </p>
        </div>
      </div>
    </div>
  )
}
