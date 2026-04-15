import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
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

  // Sync i18n language when settings change
  useEffect(() => {
    if (settings.language && i18n.language !== settings.language) {
      i18n.changeLanguage(settings.language)
    }
  }, [settings.language, i18n])

  // Fetch available providers on mount
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
      .catch(() => {
        // Backend not running yet — use default list silently
      })
  }, [])

  const handleNewChat = () => {
    clearMessages()
    // On mobile, close sidebar after starting a new chat
    if (window.innerWidth < 1024) {
      setSidebarOpen(false)
    }
  }

  const handleOpenSettings = () => {
    setSettingsOpen(true)
    if (window.innerWidth < 1024) {
      setSidebarOpen(false)
    }
  }

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{ background: 'var(--bg-main)' }}
    >
      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((prev) => !prev)}
        onNewChat={handleNewChat}
        onOpenSettings={handleOpenSettings}
        currentProvider={settings.provider}
        currentModel={settings.model}
      />

      {/* Main content — no header bar */}
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
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

      {/* Settings overlay */}
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
