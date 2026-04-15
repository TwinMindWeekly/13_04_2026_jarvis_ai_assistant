import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { PanelLeft, ChevronDown } from 'lucide-react'
import { Toast, ToastContainer } from 'react-bootstrap'
import { useAgent } from './hooks/useAgent'
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
    clearMessages,
    dismissError,
  } = useAgent(settings.provider, settings.model)

  const voiceLang = settings.language === 'vi' ? 'vi-VN' : 'en-US'
  const voice = useVoice({
    language: voiceLang,
    onTranscript: (text) => { if (text) sendMessage(text) },
    enabled: settings.voiceEnabled !== false,
  })

  // Auto TTS for assistant responses when voice mode is on
  useEffect(() => {
    if (settings.voiceEnabled === false) return
    if (messages.length === 0) return
    const last = messages[messages.length - 1]
    if (last.role === 'assistant' && last.content) {
      voice.speak(last.content, settings.ttsVoice)
    }
  }, [messages.length]) // eslint-disable-line react-hooks/exhaustive-deps

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

              <div style={{ width: 40 }} />
            </header>

            <ChatArea
              messages={messages}
              actions={actions}
              isLoading={isLoading}
              streamingText={streamingText}
              error={error}
              onSendMessage={sendMessage}
              onClear={clearMessages}
              voice={voice}
              selectedDoc={selectedDoc}
              onDocApplied={() => setEditorRefreshKey((k) => k + 1)}
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
