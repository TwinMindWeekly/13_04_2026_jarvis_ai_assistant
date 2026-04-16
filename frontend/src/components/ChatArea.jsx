import { useRef, useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertCircle, FileText, Check } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import MessageBubble from './MessageBubble'
import ActionViewer from './ActionViewer'
import ChatInput from './ChatInput'
import { vaultAPI } from '../services/api'

export default function ChatArea({
  messages = [],
  actions = [],
  isLoading = false,
  streamingText = '',
  error = null,
  onSendMessage,
  onClear,
  onCancel,
  voice = {},
  selectedDoc = null,
  onDocApplied,
  attachments = {},
  suggestionChips = null,
  emptyTitle = null,
  voiceEnabled = false,
  onToggleVoice,
  speakingCharIndex = -1,
}) {
  const { t } = useTranslation()
  const [appliedIdx, setAppliedIdx] = useState(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText, actions])

  useEffect(() => { setAppliedIdx(null) }, [selectedDoc?.id])

  const handleApply = useCallback(async (content, msgIdx) => {
    if (!selectedDoc) return
    if (!window.confirm(t('chat.applyConfirm', 'This will overwrite the document content. Continue?'))) return
    try {
      await vaultAPI.save(selectedDoc.id, content)
      setAppliedIdx(msgIdx)
      onDocApplied?.()
    } catch (err) {
      console.error('[ChatArea] Apply failed:', err)
    }
  }, [selectedDoc, onDocApplied, t])

  const showStreaming = streamingText.length > 0
  const showActions = actions.length > 0 || (isLoading && !showStreaming)
  const isEmpty = messages.length === 0 && !showStreaming && !showActions

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
              {emptyTitle || t('chat.greeting', 'What\u2019s on the agenda today?')}
            </h1>

            <div className="w-100 d-flex justify-content-center">
              <ChatInput
                isLoading={isLoading}
                onSendMessage={onSendMessage}
                onCancel={onCancel}
                voice={voice}
                selectedDoc={selectedDoc}
                onDocApplied={onDocApplied}
                attachments={attachments}
                voiceEnabled={voiceEnabled}
                onToggleVoice={onToggleVoice}
                suggestionChips={suggestionChips}
              />
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
          {messages.map((msg, idx) => {
            const isLastAssistant = msg.role === 'assistant' && idx === messages.length - 1
            const charIdx = isLastAssistant ? speakingCharIndex : -1
            return (
            <div key={idx}>
              <MessageBubble message={msg} isStreaming={false} speakingCharIndex={charIdx} />
              {msg.role === 'assistant' && selectedDoc && (
                <div style={{ maxWidth: 768, margin: '0 auto', padding: '0 24px' }}>
                  <button
                    className={`chat-apply-btn ${appliedIdx === idx ? 'applied' : ''}`}
                    onClick={() => handleApply(msg.content, idx)}
                    disabled={appliedIdx === idx}
                  >
                    {appliedIdx === idx ? (
                      <>
                        <Check size={14} />
                        <span>{t('chat.applied', 'Applied')}</span>
                      </>
                    ) : (
                      <>
                        <FileText size={14} />
                        <span>{t('chat.applyToDoc', 'Apply to document')}</span>
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
            )
          })}
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
          <ChatInput
            isLoading={isLoading}
            onSendMessage={onSendMessage}
            onCancel={onCancel}
            voice={voice}
            selectedDoc={selectedDoc}
            onDocApplied={onDocApplied}
            attachments={attachments}
            voiceEnabled={voiceEnabled}
            onToggleVoice={onToggleVoice}
          />
        </div>
      </div>
    </div>
  )
}
