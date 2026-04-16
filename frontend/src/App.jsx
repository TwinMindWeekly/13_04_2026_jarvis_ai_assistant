import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { PanelLeft, ChevronDown } from 'lucide-react'
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

  const voiceLang = settings.language === 'vi' ? 'vi-VN' : 'en-US'
  const voice = useVoice({
    language: voiceLang,
    onTranscript: (text) => { if (text) sendMessage(text) },
    enabled: settings.voiceEnabled !== false,
  })

  // Streaming TTS: speak sentence-by-sentence as text arrives
  const spokenIndexRef = useRef(0)

  useEffect(() => {
    if (settings.voiceEnabled === false) return
    if (!streamingText) {
      spokenIndexRef.current = 0
      return
    }

    const unspoken = streamingText.slice(spokenIndexRef.current)
    // Match complete sentences ending with . ! ? or newline
    const sentenceRegex = /[^.!?\n]+[.!?\n]+/g
    let match
    while ((match = sentenceRegex.exec(unspoken)) !== null) {
      const sentence = match[0].trim()
      if (sentence.length > 2) {
        voice.speak(sentence, settings.ttsVoice, { append: true })
      }
      spokenIndexRef.current += match.index + match[0].length
    }
  }, [streamingText]) // eslint-disable-line react-hooks/exhaustive-deps

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

  const handleSelectDocument = useCallback((doc) => {
    setSelectedDoc(doc)
    setViewMode('chat')
    if (window.innerWidth < 1024) setSidebarOpen(false)
  }, [])

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
                <button className="chat-header-title-btn">
                  JARVIS
                  <ChevronDown size={16} style={{ color: 'var(--text-muted)' }} />
                </button>
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
