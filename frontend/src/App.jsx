import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { PanelLeft } from 'lucide-react'
import JarvisOrb from './components/JarvisOrb'
import { Toast, ToastContainer } from 'react-bootstrap'
import { useAgent } from './hooks/useAgent'
import { useAttachments } from './hooks/useAttachments'
import { useSettings } from './hooks/useSettings'
import { useVoice } from './hooks/useVoice'
import { chatAPI } from './services/api'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'
import SettingsPanel from './components/SettingsPanel'
import GraphPage from './components/GraphPage'
import MarkdownEditorPanel from './components/MarkdownEditorPanel'
import ResizeHandle from './components/ResizeHandle'

const SPLIT_MIN_PX = 280

/** Strip markdown → plain text before TTS sentence splitting. */
function stripMarkdown(text) {
  return text
    .replace(/```[\s\S]*?```/g, '')              // code blocks
    .replace(/!\[.*?\]\(.+?\)/g, '')              // images
    .replace(/\[(.+?)\]\(.+?\)/g, '$1')          // links
    .replace(/<[^>]+>/g, '')                       // HTML tags
    .replace(/^#{1,6}\s+/gm, '')                  // headings
    .replace(/^\s*>\s*/gm, '')                     // blockquotes
    .replace(/^-{3,}$/gm, '')                      // horizontal rules
    .replace(/^\s*[-*+]\s{1,4}/gm, '')            // bullets (* - +)
    .replace(/^\s*(\d+)\.\s+/gm, '$1, ')          // numbered lists → "1, "
    .replace(/\*{2}(.+?)\*{2}/g, '$1')            // **bold**
    .replace(/\*(.+?)\*/g, '$1')                   // *italic*
    .replace(/__(.+?)__/g, '$1')                    // __bold__
    .replace(/_(.+?)_/g, '$1')                      // _italic_
    .replace(/`(.+?)`/g, '$1')                      // `code`
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

/**
 * Chia plain text thành các chunk nhỏ cho TTS.
 * Thứ tự: newline (line break) → sentence (. ! ? 。 ？ ！ + space).
 * Gộp các câu liền nhau tới targetSize để tránh request vụn.
 * Câu dài hơn targetSize vẫn gửi nguyên — không cắt giữa câu.
 */
function splitIntoSpeakChunks(text, targetSize = 300) {
  if (!text) return []
  const lines = text.split(/\n+/).map((s) => s.trim()).filter(Boolean)
  const chunks = []
  for (const line of lines) {
    const sentences = line
      .split(/(?<=[.!?。？！])\s+/)
      .map((s) => s.trim())
      .filter(Boolean)
    let buf = ''
    for (const sent of sentences) {
      if (!buf) {
        buf = sent
      } else if (buf.length + 1 + sent.length <= targetSize) {
        buf = `${buf} ${sent}`
      } else {
        chunks.push(buf)
        buf = sent
      }
    }
    if (buf) chunks.push(buf)
  }
  return chunks
}

export default function App() {
  const { t, i18n } = useTranslation()
  const { settings, updateSettings } = useSettings()

  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [viewMode, setViewMode] = useState('chat') // 'chat' | 'graph'
  const [providers, setProviders] = useState([])
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [splitRatio, setSplitRatio] = useState(0.4)
  const [editorRefreshKey, setEditorRefreshKey] = useState(0)
  const splitRef = useRef(null)

  const {
    messages,
    actions,
    isLoading,
    error,
    streamingText,
    sendMessage,
    cancelRequest,
    clearMessages,
    dismissError,
  } = useAgent(settings.provider, settings.model, settings.language)

  const chatAttachments = useAttachments()

  const sttLang = settings.language === 'vi' ? 'vi-VN' : 'en-US'
  const voice = useVoice({
    language: sttLang,  // only affects STT; TTS uses VieNeu backend (bilingual)
    onTranscript: (text) => { if (text) sendMessage(text) },
    enabled: settings.voiceEnabled !== false,
  })

  // Streaming TTS: speak paragraph-by-paragraph as text arrives (WS path).
  // Indexing in markdown coordinates so the highlight lines up with rendered paragraphs.
  const spokenParagraphCountRef = useRef(0)
  const lastSpokenMsgCount = useRef(0)

  const speakParagraphRange = useCallback((markdown, startIndex, endIndex) => {
    const paragraphs = markdown.split(/\n\n+/)
    const end = Math.min(endIndex, paragraphs.length)
    for (let i = startIndex; i < end; i++) {
      const stripped = stripMarkdown(paragraphs[i]).trim()
      if (stripped.length <= 2) continue
      const chunks = splitIntoSpeakChunks(stripped)
      for (const chunk of chunks) {
        voice.speak(chunk, settings.ttsVoice, { append: true, paragraphIndex: i })
      }
    }
  }, [voice, settings.ttsVoice])

  useEffect(() => {
    if (settings.voiceEnabled === false) return
    if (!streamingText) return

    const paragraphs = streamingText.split(/\n\n+/)
    // Last paragraph may still be streaming — only speak it if message ends with \n\n.
    const completeCount = /\n\n+\s*$/.test(streamingText) ? paragraphs.length : paragraphs.length - 1
    if (completeCount > spokenParagraphCountRef.current) {
      speakParagraphRange(streamingText, spokenParagraphCountRef.current, completeCount)
      spokenParagraphCountRef.current = completeCount
    }
  }, [streamingText, settings.voiceEnabled, speakParagraphRange])

  // When message completes: speak any paragraphs streaming didn't cover.
  useEffect(() => {
    if (settings.voiceEnabled === false) return
    if (messages.length === 0 || messages.length <= lastSpokenMsgCount.current) return
    const last = messages[messages.length - 1]
    if (last.role === 'assistant' && last.content) {
      const total = last.content.split(/\n\n+/).length
      speakParagraphRange(last.content, spokenParagraphCountRef.current, total)
    }
    lastSpokenMsgCount.current = messages.length
    spokenParagraphCountRef.current = 0  // reset for next message
  }, [messages.length, settings.voiceEnabled, speakParagraphRange]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (settings.language && i18n.language !== settings.language) {
      i18n.changeLanguage(settings.language)
    }
  }, [settings.language, i18n])

  useEffect(() => {
    chatAPI
      .getProviders()
      .then(({ data }) => {
        if (Array.isArray(data?.providers)) {
          setProviders(data.providers)
        } else if (Array.isArray(data)) {
          setProviders(data)
        }
      })
      .catch(() => {})
  }, [])

  const handleToggleVoice = useCallback(() => {
    const currentlyEnabled = settings.voiceEnabled !== false
    updateSettings({ voiceEnabled: !currentlyEnabled })
    if (currentlyEnabled) {
      voice.stopSpeaking()
    }
  }, [settings.voiceEnabled, updateSettings, voice])

  const handleNewChat = () => {
    clearMessages()
    setSelectedDoc(null)
    if (window.innerWidth < 1024) setSidebarOpen(false)
  }

  const handleOpenSettings = () => {
    setSettingsOpen(true)
    if (window.innerWidth < 1024) setSidebarOpen(false)
  }

  const [graphSelectedDoc, setGraphSelectedDoc] = useState(null)

  const handleSelectDocument = useCallback((doc) => {
    if (viewMode === 'graph') {
      setGraphSelectedDoc(doc)
    } else {
      setSelectedDoc(doc)
    }
    if (window.innerWidth < 1024) setSidebarOpen(false)
  }, [viewMode])

  const handleSplitResize = useCallback((delta) => {
    const container = splitRef.current
    if (!container) return
    const totalW = container.offsetWidth
    if (totalW <= 0) return
    setSplitRatio((prev) => {
      const leftPx = prev * totalW + delta
      const clamped = Math.max(SPLIT_MIN_PX, Math.min(totalW - SPLIT_MIN_PX, leftPx))
      return clamped / totalW
    })
  }, [])

  // Paragraph index for TTS highlight in MessageBubble (-1 when not speaking)
  const speakingParagraphIndex = (settings.voiceEnabled !== false && voice.isSpeaking) ? voice.speakingParagraphIndex : -1

  return (
    <div className="d-flex" style={{ height: '100vh', overflow: 'hidden', background: 'var(--bg-main)' }}>
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((prev) => !prev)}
        onNewChat={handleNewChat}
        onOpenSettings={handleOpenSettings}
        onOpenGraph={() => setViewMode('graph')}
        onSelectDocument={handleSelectDocument}
        selectedDocId={selectedDoc?.id}
        currentProvider={settings.provider}
        currentModel={settings.model}
      />

      {viewMode === 'graph' ? (
        <GraphPage
          onBack={() => setViewMode('chat')}
          settings={settings}
          externalSelectedDoc={graphSelectedDoc}
          onExternalDocConsumed={() => setGraphSelectedDoc(null)}
        />
      ) : (
        <div className="chat-split-wrapper" ref={splitRef}>
          {/* MD Editor on the left when a document is selected */}
          {selectedDoc && (
            <>
              <div
                className="chat-split-editor"
                style={{ flex: `0 0 ${splitRatio * 100}%` }}
              >
                <MarkdownEditorPanel
                  selected={selectedDoc}
                  onClose={() => setSelectedDoc(null)}
                  refreshKey={editorRefreshKey}
                />
              </div>
              <ResizeHandle onResize={handleSplitResize} />
            </>
          )}

          {/* Chat area on the right (or full width) */}
          <main className="chat-main" style={selectedDoc ? { flex: `0 0 ${(1 - splitRatio) * 100}%` } : undefined}>
            {/* Minimal header */}
            <header className="chat-header">
              {!sidebarOpen && (
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="sidebar-icon-btn"
                  aria-label="Open sidebar"
                >
                  <PanelLeft size={20} />
                </button>
              )}

              <div className="flex-grow-1 d-flex align-items-center justify-content-center">
                <JarvisOrb
                  status={isLoading ? 'loading' : voice.isSpeaking ? 'speaking' : error ? 'error' : 'idle'}
                />
              </div>

              <div className="d-flex align-items-center gap-1">
                {['en', 'vi'].map((code) => (
                  <button
                    key={code}
                    onClick={() => updateSettings({ language: code })}
                    className="lang-toggle-btn"
                    style={{
                      padding: '2px 8px',
                      fontSize: '0.72rem',
                      fontWeight: settings.language === code ? 700 : 400,
                      background: settings.language === code ? 'var(--accent)' : 'transparent',
                      color: settings.language === code ? '#fff' : 'var(--text-muted)',
                      border: settings.language === code ? 'none' : '1px solid var(--border)',
                      borderRadius: 4,
                      cursor: 'pointer',
                    }}
                  >
                    {code.toUpperCase()}
                  </button>
                ))}
              </div>
            </header>

            <ChatArea
              messages={messages}
              actions={actions}
              isLoading={isLoading}
              streamingText={streamingText}
              error={error}
              onSendMessage={sendMessage}
              onCancel={cancelRequest}
              onClear={clearMessages}
              voice={voice}
              attachments={chatAttachments}
              selectedDoc={selectedDoc}
              onDocApplied={() => setEditorRefreshKey((k) => k + 1)}
              voiceEnabled={settings.voiceEnabled !== false}
              onToggleVoice={handleToggleVoice}
              speakingParagraphIndex={speakingParagraphIndex}
            />
          </main>
        </div>
      )}

      <SettingsPanel
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onUpdateSettings={updateSettings}
        providers={providers}
      />

      {/* Error toast */}
      <ToastContainer position="bottom-end" className="p-3" style={{ zIndex: 9999 }}>
        <Toast
          show={!!error}
          onClose={dismissError}
          delay={6000}
          autohide
          bg="danger"
        >
          <Toast.Header closeButton>
            <strong className="me-auto">{t('toast.errorTitle', 'Error')}</strong>
          </Toast.Header>
          <Toast.Body className="text-white">{error}</Toast.Body>
        </Toast>
      </ToastContainer>
    </div>
  )
}
