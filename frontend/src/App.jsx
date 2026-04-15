import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { Menu, Settings, Zap } from 'lucide-react'
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
      style={{ background: 'var(--surface)' }}
    >
      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((prev) => !prev)}
        onNewChat={handleNewChat}
        onOpenSettings={handleOpenSettings}
      />

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Header */}
        <header
          className="flex-shrink-0 flex items-center gap-3 px-4 py-3"
          style={{
            borderBottom: '1px solid var(--glass-border)',
            background: 'rgba(15,15,35,0.8)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
          }}
        >
          {/* Sidebar toggle */}
          <motion.button
            onClick={() => setSidebarOpen((prev) => !prev)}
            className="w-8 h-8 rounded-xl flex items-center justify-center transition-colors hover:bg-white/10 flex-shrink-0"
            whileTap={{ scale: 0.9 }}
            aria-label="Toggle sidebar"
          >
            <Menu size={16} style={{ color: 'var(--text-secondary)' }} />
          </motion.button>

          {/* Title */}
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <div
              className="w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{
                background: 'rgba(99,102,241,0.2)',
                border: '1px solid rgba(99,102,241,0.35)',
              }}
            >
              <Zap size={12} style={{ color: 'var(--accent)' }} />
            </div>
            <span
              className="text-sm font-semibold truncate"
              style={{ color: 'var(--text-primary)' }}
            >
              {t('app.title')}
            </span>

            {/* Provider / model pill */}
            <span
              className="hidden sm:inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium flex-shrink-0"
              style={{
                background: 'rgba(99,102,241,0.1)',
                border: '1px solid rgba(99,102,241,0.2)',
                color: 'var(--text-muted)',
              }}
            >
              {settings.provider} · {settings.model}
            </span>
          </div>

          {/* Settings button */}
          <motion.button
            onClick={() => setSettingsOpen(true)}
            className="w-8 h-8 rounded-xl flex items-center justify-center transition-colors hover:bg-white/10 flex-shrink-0"
            whileTap={{ scale: 0.9 }}
            aria-label={t('settings.title')}
          >
            <Settings size={16} style={{ color: 'var(--text-secondary)' }} />
          </motion.button>
        </header>

        {/* Chat fills the remaining vertical space */}
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
