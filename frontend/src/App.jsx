import { useState, useEffect } from 'react'
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
import DocumentsPanel from './components/DocumentsPanel'
import GraphPanel from './components/GraphPanel'

export default function App() {
  const { t, i18n } = useTranslation()
  const { settings, updateSettings } = useSettings()

  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [documentsOpen, setDocumentsOpen] = useState(false)
  const [graphOpen, setGraphOpen] = useState(false)
  const [providers, setProviders] = useState([])

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
    if (window.innerWidth < 1024) setSidebarOpen(false)
  }

  const handleOpenSettings = () => {
    setSettingsOpen(true)
    if (window.innerWidth < 1024) setSidebarOpen(false)
  }

  return (
    <div className="d-flex" style={{ height: '100vh', overflow: 'hidden', background: 'var(--bg-main)' }}>
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((prev) => !prev)}
        onNewChat={handleNewChat}
        onOpenSettings={handleOpenSettings}
        onOpenDocuments={() => setDocumentsOpen(true)}
        onOpenGraph={() => setGraphOpen(true)}
        currentProvider={settings.provider}
        currentModel={settings.model}
      />

      <main className="chat-main">
        {/* Minimal header */}
        <header className="chat-header">
          {/* Sidebar toggle — only when sidebar is closed */}
          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="sidebar-icon-btn"
              aria-label="Open sidebar"
            >
              <PanelLeft size={20} />
            </button>
          )}

          {/* App title — centered */}
          <div className="flex-grow-1 d-flex align-items-center justify-content-center">
            <button className="chat-header-title-btn">
              JARVIS
              <ChevronDown size={16} style={{ color: 'var(--text-muted)' }} />
            </button>
          </div>

          {/* Spacer to balance sidebar toggle */}
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
        />
      </main>

      <SettingsPanel
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onUpdateSettings={updateSettings}
        providers={providers}
      />

      <DocumentsPanel
        isOpen={documentsOpen}
        onClose={() => setDocumentsOpen(false)}
      />

      <GraphPanel
        isOpen={graphOpen}
        onClose={() => setGraphOpen(false)}
      />

      {/* Error toast — shows when backend is unreachable or API errors */}
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
