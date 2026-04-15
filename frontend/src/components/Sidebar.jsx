import { motion, AnimatePresence } from 'framer-motion'
import { SquarePen, Settings, MessageSquare, X, Zap } from 'lucide-react'
import { useTranslation } from 'react-i18next'

const SIDEBAR_WIDTH = 260

export default function Sidebar({
  isOpen,
  onToggle,
  onNewChat,
  onOpenSettings,
  currentProvider,
  currentModel,
}) {
  const { t } = useTranslation()

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            key="overlay"
            className="fixed inset-0 z-20 lg:hidden"
            style={{ background: 'rgba(0,0,0,0.6)' }}
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
        transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="relative flex-shrink-0 h-full overflow-hidden z-30 lg:relative lg:z-auto"
      >
        <div
          className="absolute inset-0 flex flex-col"
          style={{
            width: SIDEBAR_WIDTH,
            background: 'var(--bg-sidebar)',
            borderRight: '1px solid var(--border-light)',
          }}
        >
          {/* Top: New Chat button */}
          <div className="flex items-center gap-2 px-3 pt-4 pb-2">
            <button
              onClick={onNewChat}
              className="flex-1 flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150"
              style={{ color: 'var(--text-primary)' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--bg-hover)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
              }}
            >
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0"
                style={{ background: 'var(--accent)' }}
              >
                <Zap size={14} color="#fff" />
              </div>
              <span className="font-semibold">JARVIS</span>
            </button>

            <button
              onClick={onNewChat}
              className="flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center transition-colors duration-150"
              style={{ color: 'var(--text-secondary)' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--bg-hover)'
                e.currentTarget.style.color = 'var(--text-primary)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.color = 'var(--text-secondary)'
              }}
              aria-label={t('sidebar.newChat')}
              title={t('sidebar.newChat')}
            >
              <SquarePen size={17} />
            </button>

            <button
              onClick={onToggle}
              className="flex-shrink-0 w-9 h-9 rounded-lg lg:hidden flex items-center justify-center transition-colors duration-150"
              style={{ color: 'var(--text-secondary)' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--bg-hover)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
              }}
              aria-label="Close sidebar"
            >
              <X size={16} />
            </button>
          </div>

          {/* Chat history section */}
          <div className="flex-1 px-2 py-2 overflow-y-auto">
            <p
              className="text-xs font-medium px-3 py-2"
              style={{ color: 'var(--text-muted)' }}
            >
              {t('sidebar.history')}
            </p>
            <div className="flex flex-col items-center justify-center gap-2 py-10">
              <MessageSquare size={18} style={{ color: 'var(--text-muted)' }} />
              <span
                className="text-xs text-center"
                style={{ color: 'var(--text-muted)' }}
              >
                No conversations yet
              </span>
            </div>
          </div>

          {/* Bottom: provider info + settings */}
          <div
            className="px-2 pb-3 pt-2"
            style={{ borderTop: '1px solid var(--border-light)' }}
          >
            {currentProvider && currentModel && (
              <div
                className="px-3 py-2 mb-1 rounded-lg text-xs"
                style={{ color: 'var(--text-muted)' }}
              >
                {currentProvider} · {currentModel}
              </div>
            )}
            <button
              onClick={onOpenSettings}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm transition-colors duration-150"
              style={{ color: 'var(--text-secondary)' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--bg-hover)'
                e.currentTarget.style.color = 'var(--text-primary)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.color = 'var(--text-secondary)'
              }}
            >
              <Settings size={16} />
              {t('sidebar.settings')}
            </button>
          </div>
        </div>
      </motion.aside>
    </>
  )
}
