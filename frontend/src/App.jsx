import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { PanelLeft, ChevronDown } from 'lucide-react'
import { useAgent } from './hooks/useAgent'
import { useSettings } from './hooks/useSettings'
import { chatAPI } from './services/api'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'
import SettingsPanel from './components/SettingsPanel'

export default function App() {
  const { t, i18n } = useTranslation()
  const { settings, updateSettings } = useSettings()

  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [providers, setProviders] = useState([])

  const {
    messages,
    actions,
    isLoading,
    error,
    streamingText,
    sendMessage,
    clearMessages,
  } = useAgent(settings.provider, settings.model)

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
    <div
      className="flex h-screen overflow-hidden"
      style={{ background: 'var(--bg-main)' }}
    >
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((prev) => !prev)}
        onNewChat={handleNewChat}
        onOpenSettings={handleOpenSettings}
        currentProvider={settings.provider}
        currentModel={settings.model}
      />

      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Minimal header like ChatGPT */}
        <header
          className="flex-shrink-0 flex items-center h-12 px-3"
          style={{ background: 'var(--bg-main)' }}
        >
          {/* Sidebar toggle */}
          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="w-10 h-10 rounded-lg flex items-center justify-center transition-colors"
              style={{ color: 'var(--text-secondary)' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--bg-hover)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
              }}
              aria-label="Open sidebar"
            >
              <PanelLeft size={20} />
            </button>
          )}

          {/* App title — center */}
          <div className="flex-1 flex items-center justify-center">
            <button
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-base font-semibold transition-colors"
              style={{ color: 'var(--text-primary)' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--bg-hover)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
              }}
            >
              JARVIS
              <ChevronDown size={16} style={{ color: 'var(--text-muted)' }} />
            </button>
          </div>

          {/* Spacer to balance sidebar toggle */}
          <div className="w-10" />
        </header>

        <ChatArea
          messages={messages}
          actions={actions}
          isLoading={isLoading}
          streamingText={streamingText}
          error={error}
          onSendMessage={sendMessage}
          onClear={clearMessages}
        />
      </main>

      <SettingsPanel
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onUpdateSettings={updateSettings}
        providers={providers}
      />
    </div>
  )
}
