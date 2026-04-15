import { motion, AnimatePresence } from 'framer-motion'
import { Bot, Plus, Settings, MessageSquare, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

const SIDEBAR_WIDTH = 260

export default function Sidebar({ isOpen, onToggle, onNewChat, onOpenSettings }) {
  const { t } = useTranslation()

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            key="overlay"
            className="fixed inset-0 z-20 lg:hidden"
            style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(2px)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onToggle}
          />
        )}
      </AnimatePresence>

      {/* Sidebar panel */}
      <motion.aside
        initial={false}
        animate={{ width: isOpen ? SIDEBAR_WIDTH : 0 }}
        transition={{ duration: 0.28, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="relative flex-shrink-0 h-full overflow-hidden z-30 lg:relative lg:z-auto"
        style={{
          position: undefined,
        }}
      >
        <div
          className="absolute inset-0 flex flex-col"
          style={{
            width: SIDEBAR_WIDTH,
            background: 'var(--glass-bg)',
            borderRight: '1px solid var(--glass-border)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
          }}
        >
          {/* Logo / Title */}
          <div
            className="flex items-center gap-3 px-5 py-5"
            style={{ borderBottom: '1px solid var(--glass-border)' }}
          >
            <div
              className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{
                background: 'linear-gradient(135deg, rgba(99,102,241,0.6) 0%, rgba(99,102,241,0.2) 100%)',
                border: '1px solid rgba(99,102,241,0.4)',
                boxShadow: '0 0 16px rgba(99,102,241,0.25)',
              }}
            >
              <Bot size={16} style={{ color: '#c7d2fe' }} />
            </div>
            <div className="flex flex-col min-w-0">
              <span
                className="text-sm font-bold tracking-tight truncate"
                style={{ color: 'var(--text-primary)' }}
              >
                JARVIS
              </span>
              <span
                className="text-[10px] truncate"
                style={{ color: 'var(--text-muted)' }}
              >
                AI Assistant
              </span>
            </div>

            <button
              onClick={onToggle}
              className="ml-auto lg:hidden flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center transition-colors hover:bg-white/10"
              aria-label="Close sidebar"
            >
              <X size={14} style={{ color: 'var(--text-secondary)' }} />
            </button>
          </div>

          {/* New Chat button */}
          <div className="px-4 pt-4">
            <button
              onClick={onNewChat}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 group"
              style={{
                background: 'rgba(99,102,241,0.12)',
                border: '1px solid rgba(99,102,241,0.25)',
                color: 'var(--text-primary)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(99,102,241,0.22)'
                e.currentTarget.style.borderColor = 'rgba(99,102,241,0.45)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(99,102,241,0.12)'
                e.currentTarget.style.borderColor = 'rgba(99,102,241,0.25)'
              }}
            >
              <Plus size={15} style={{ color: 'var(--accent)' }} />
              {t('sidebar.newChat')}
            </button>
          </div>

          {/* Chat history section */}
          <div className="flex-1 px-4 py-4 overflow-y-auto">
            <p
              className="text-[10px] font-semibold uppercase tracking-widest mb-3 px-1"
              style={{ color: 'var(--text-muted)' }}
            >
              {t('sidebar.history')}
            </p>
            <div
              className="flex flex-col items-center justify-center gap-2 py-8 rounded-xl"
              style={{
                background: 'rgba(255,255,255,0.02)',
                border: '1px dashed rgba(255,255,255,0.08)',
              }}
            >
              <MessageSquare size={20} style={{ color: 'var(--text-muted)' }} />
              <span
                className="text-xs text-center"
                style={{ color: 'var(--text-muted)' }}
              >
                Chat history coming soon
              </span>
            </div>
          </div>

          {/* Settings button at bottom */}
          <div
            className="px-4 pb-5 pt-3"
            style={{ borderTop: '1px solid var(--glass-border)' }}
          >
            <button
              onClick={onOpenSettings}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm transition-all duration-150"
              style={{
                color: 'var(--text-secondary)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
                e.currentTarget.style.color = 'var(--text-primary)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.color = 'var(--text-secondary)'
              }}
            >
              <Settings size={15} />
              {t('sidebar.settings')}
            </button>
          </div>
        </div>
      </motion.aside>
    </>
  )
}
