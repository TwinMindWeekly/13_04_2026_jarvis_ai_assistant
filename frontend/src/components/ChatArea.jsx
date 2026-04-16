import { useRef, useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowUp, Plus, AlertCircle, Mic, FileText, Check, X, Square, Volume2, VolumeX } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import MessageBubble from './MessageBubble'
import ActionViewer from './ActionViewer'
import VoiceButton from './VoiceButton'
import AttachmentPreview from './AttachmentPreview'
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
}) {
  const { t } = useTranslation()
  const [input, setInput] = useState('')
  const [appliedIdx, setAppliedIdx] = useState(null)
  const [docContextOn, setDocContextOn] = useState(true)
  const [dragOver, setDragOver] = useState(false)
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText, actions])

  // Reset context toggle + applied state when doc changes.
  useEffect(() => { setDocContextOn(true) }, [selectedDoc?.id])
  useEffect(() => { setAppliedIdx(null) }, [selectedDoc?.id])

  const handleInputChange = useCallback((e) => {
    const el = e.target
    setInput(el.value)
    el.style.height = 'auto'
    const maxHeight = 28 * 6
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
  }, [])

  const handleSend = useCallback(async () => {
    const trimmed = input.trim()
    if (!trimmed || isLoading) return

    // If a doc is selected AND context toggle is on, fetch content as context.
    let docContext = null
    if (selectedDoc && docContextOn) {
      try {
        const { data } = await vaultAPI.get(selectedDoc.id)
        docContext = { filename: selectedDoc.label || selectedDoc.filename, content: data.content }
      } catch {
        // Send without context if vault fetch fails.
      }
    }

    // Serialize attachments into the message
    let fullMessage = trimmed
    const attachmentText = attachments.serializeForPrompt?.() || ''
    if (attachmentText) {
      fullMessage = `${attachmentText}\n\n${trimmed}`
    }

    onSendMessage(fullMessage, docContext)
    setInput('')
    attachments.clearAttachments?.()
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [input, isLoading, onSendMessage, selectedDoc, docContextOn, attachments])

  const handleFileSelect = useCallback((e) => {
    const files = Array.from(e.target.files || [])
    files.forEach((f) => attachments.addFile?.(f))
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [attachments])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const files = Array.from(e.dataTransfer.files || [])
    files.forEach((f) => attachments.addFile?.(f))
  }, [attachments])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setDragOver(false)
  }, [])

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend]
  )

  const handleApply = useCallback(async (content, msgIdx) => {
    if (!selectedDoc) return
    try {
      await vaultAPI.save(selectedDoc.id, content)
      setAppliedIdx(msgIdx)
      onDocApplied?.()
    } catch {
      // silent
    }
  }, [selectedDoc, onDocApplied])

  const hasAttachments = (attachments.attachments?.length || 0) > 0
  const canSend = (input.trim().length > 0 || hasAttachments) && !isLoading
  const showStreaming = streamingText.length > 0
  const showActions = actions.length > 0 || (isLoading && !showStreaming)
  const isEmpty = messages.length === 0 && !showStreaming && !showActions

  /* Shared input bar — centered, max 768px like ChatGPT */
  const inputBar = (
    <div style={{ width: '100%', maxWidth: 768, margin: '0 auto', padding: '0 16px' }}>
      {/* Doc context toggle badge */}
      {selectedDoc && (
        <button
          className={`chat-doc-context-badge ${docContextOn ? '' : 'off'}`}
          onClick={() => setDocContextOn((v) => !v)}
          title={docContextOn ? t('chat.contextOn', 'Document context ON — click to disable') : t('chat.contextOff', 'Document context OFF — click to enable')}
        >
          <FileText size={13} />
          <span>{selectedDoc.label || selectedDoc.filename}</span>
          {docContextOn && <X size={12} className="chat-doc-context-x" />}
        </button>
      )}

      {/* Voice transcript preview */}
      {voice.isListening && voice.transcript && (
        <div className="voice-transcript mb-2">
          <Mic size={14} style={{ color: '#ef4444', flexShrink: 0 }} />
          <span>{voice.transcript}</span>
        </div>
      )}

      <AttachmentPreview
        attachments={attachments.attachments || []}
        uploading={attachments.uploading}
        error={attachments.uploadError}
        onRemove={attachments.removeAttachment}
      />

      <input
        ref={fileInputRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileSelect}
      />

      <div
        className={`chat-input-wrapper${dragOver ? ' drag-over' : ''}`}
        onFocus={(e) => { e.currentTarget.style.borderColor = '#555' }}
        onBlur={(e) => { e.currentTarget.style.borderColor = dragOver ? 'var(--accent)' : 'var(--border)' }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <button className="attach-btn" aria-label="Attach" onClick={() => fileInputRef.current?.click()}>
          <Plus size={20} />
        </button>

        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={
            selectedDoc && docContextOn
              ? t('chat.placeholderDoc', 'Ask AI to improve this document...')
              : t('chat.placeholder')
          }
          rows={1}
          disabled={isLoading}
          className="chat-textarea"
        />

        {/* TTS toggle — inline on chat bar */}
        {onToggleVoice && (
          <button
            className="voice-toggle-btn"
            onClick={onToggleVoice}
            aria-label={voiceEnabled ? 'Tắt giọng nói' : 'Bật giọng nói'}
            title={voiceEnabled ? 'Tắt giọng nói' : 'Bật giọng nói'}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: 8,
              display: 'flex',
              alignItems: 'center',
              color: voiceEnabled ? 'var(--accent)' : 'var(--text-muted)',
              transition: 'color 0.2s',
            }}
          >
            {voiceEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
          </button>
        )}

        <VoiceButton
          isListening={voice.isListening}
          isSpeaking={onToggleVoice ? false : voice.isSpeaking}
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
            <motion.button
              key="cancel"
              initial={{ opacity: 0, scale: 0.7 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.7 }}
              transition={{ duration: 0.15 }}
              onClick={onCancel}
              className="send-btn"
              style={{ background: 'var(--error, #ef4444)' }}
              whileTap={{ scale: 0.9 }}
              aria-label={t('chat.cancel', 'Cancel')}
              title={t('chat.cancel', 'Cancel')}
            >
              <Square size={16} fill="currentColor" />
            </motion.button>
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
              {emptyTitle || 'What\u2019s on the agenda today?'}
            </h1>

            <div className="w-100 d-flex justify-content-center">
              {inputBar}
            </div>

            {/* Suggestion chips (optional) */}
            {Array.isArray(suggestionChips) && suggestionChips.length > 0 && (
              <div className="chat-suggestion-chips">
                {suggestionChips.map((chip, i) => {
                  const label = typeof chip === 'string' ? chip : chip.label
                  const prompt = typeof chip === 'string' ? chip : (chip.prompt || chip.label)
                  return (
                    <button
                      key={i}
                      className="chat-suggestion-chip"
                      onClick={() => {
                        setInput(prompt)
                        if (textareaRef.current) {
                          textareaRef.current.focus()
                        }
                      }}
                    >
                      {label}
                    </button>
                  )
                })}
              </div>
            )}
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
            <div key={idx}>
              <MessageBubble message={msg} isStreaming={false} />
              {/* Apply button for assistant messages when a doc is open */}
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
