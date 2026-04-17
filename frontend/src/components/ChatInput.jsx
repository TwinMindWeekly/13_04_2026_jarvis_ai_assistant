import { useState, useRef, useCallback, memo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowUp, Plus, Mic, FileText, X, Square, Volume2, VolumeX } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import VoiceButton from './VoiceButton'
import AttachmentPreview from './AttachmentPreview'
import { vaultAPI } from '../services/api'

/**
 * ChatInput — isolated input component.
 * Manages its own `input` state so that keystrokes don't re-render the message list.
 */
function ChatInput({
  isLoading = false,
  onSendMessage,
  onCancel,
  voice = {},
  selectedDoc = null,
  onDocApplied,
  attachments = {},
  voiceEnabled = false,
  onToggleVoice,
  suggestionChips = null,
  onChipClick,
}) {
  const { t } = useTranslation()
  const [input, setInput] = useState('')
  const [docContextOn, setDocContextOn] = useState(true)
  const [dragOver, setDragOver] = useState(false)
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  // Reset context toggle when doc changes
  const prevDocIdRef = useRef(selectedDoc?.id)
  if (selectedDoc?.id !== prevDocIdRef.current) {
    prevDocIdRef.current = selectedDoc?.id
    setDocContextOn(true)
  }

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

    let docContext = null
    if (selectedDoc && docContextOn) {
      try {
        const { data } = await vaultAPI.get(selectedDoc.id)
        let content = data.content || ''
        const MAX_DOC_CHARS = 8000
        if (content.length > MAX_DOC_CHARS) {
          content = content.slice(0, MAX_DOC_CHARS) + '\n\n...(truncated, original: ' + data.content.length + ' chars)'
        }
        docContext = { filename: selectedDoc.label || selectedDoc.filename, content }
      } catch {
        // Send without context if vault fetch fails.
      }
    }

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

  const hasAttachments = (attachments.attachments?.length || 0) > 0
  const canSend = (input.trim().length > 0 || hasAttachments) && !isLoading

  return (
    <div style={{ width: '100%', maxWidth: 768, margin: '0 auto', padding: '0 16px' }}>
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

      {voiceEnabled && voice.voiceMissing && (
        <div className="voice-missing-warning">
          <span>
            {t('voice.missing', 'No voice found for this language. Install it in Windows Settings → Time & Language → Speech → Add voices.')}
          </span>
        </div>
      )}

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

        {onToggleVoice && (
          <button
            className={`voice-toggle-btn${voice.isSpeaking ? ' speaking' : ''}`}
            onClick={voice.isSpeaking ? voice.stopSpeaking : onToggleVoice}
            aria-label={voice.isSpeaking ? 'Stop' : voiceEnabled ? 'Mute' : 'Unmute'}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              color: voice.isSpeaking ? 'var(--accent)' : voiceEnabled ? 'var(--accent)' : 'var(--text-muted)',
              transition: 'color 0.2s',
            }}
          >
            {voiceEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
            {voice.isSpeaking && (
              <>
                <span className="voice-pulse-ring" />
                <span className="voice-pulse-ring delay" />
              </>
            )}
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
        {t('chat.disclaimer', 'JARVIS can make mistakes. Consider checking important info.')}
      </p>

      {/* Suggestion chips (used by GraphPage empty state) */}
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
                  textareaRef.current?.focus()
                }}
              >
                {label}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default memo(ChatInput)
