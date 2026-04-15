import { motion, AnimatePresence } from 'framer-motion'
import { SquarePen, Settings, MessageSquare, X, Zap, Search, Globe, Monitor, PanelLeft } from 'lucide-react'
import { useTranslation } from 'react-i18next'

const SIDEBAR_WIDTH = 260

const MENU_ITEMS = [
  { icon: Search, label: 'Search chats' },
  { icon: Globe, label: 'Web Search' },
  { icon: Monitor, label: 'Screen Capture' },
]

function SidebarButton({ icon: Icon, label, onClick, size = 18 }) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors duration-150"
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
      <Icon size={size} />
      <span>{label}</span>
    </button>
  )
}

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
          }}
        >
          {/* Top: sidebar toggle + new chat */}
          <div className="flex items-center justify-between px-2 pt-3 pb-1">
            <button
              onClick={onToggle}
              className="w-10 h-10 rounded-lg flex items-center justify-center transition-colors"
              style={{ color: 'var(--text-secondary)' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--bg-hover)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
              }}
              aria-label="Toggle sidebar"
            >
              <PanelLeft size={20} />
            </button>

            <button
              onClick={onNewChat}
              className="w-10 h-10 rounded-lg flex items-center justify-center transition-colors"
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
              <SquarePen size={20} />
            </button>
          </div>

          {/* Menu items */}
          <div className="px-2 py-1">
            <SidebarButton icon={SquarePen} label={t('sidebar.newChat')} onClick={onNewChat} />
            {MENU_ITEMS.map((item) => (
              <SidebarButton key={item.label} icon={item.icon} label={item.label} />
            ))}
          </div>

          {/* Chat history section */}
          <div className="flex-1 px-2 py-2 overflow-y-auto">
            <p
              className="text-xs font-medium px-3 py-2 uppercase tracking-wider"
              style={{ color: 'var(--text-muted)' }}
            >
              Recents
            </p>
            <div className="flex flex-col items-center justify-center gap-2 py-8">
              <MessageSquare size={18} style={{ color: 'var(--text-muted)' }} />
              <span
                className="text-xs text-center"
                style={{ color: 'var(--text-muted)' }}
              >
                No conversations yet
              </span>
            </div>
          </div>

          {/* Bottom: user area + settings */}
          <div
            className="px-2 pb-3 pt-2"
            style={{ borderTop: '1px solid var(--border-light)' }}
          >
            {/* Provider info */}
            {currentProvider && currentModel && (
              <div
                className="flex items-center gap-2 px-3 py-2 mb-1 rounded-lg text-xs"
                style={{ color: 'var(--text-muted)' }}
              >
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{ background: 'var(--accent)' }}
                >
                  <Zap size={10} color="#fff" />
                </div>
                <span>{currentProvider} · {currentModel}</span>
              </div>
            )}

            <SidebarButton icon={Settings} label={t('sidebar.settings')} onClick={onOpenSettings} />
          </div>
        </div>
      </motion.aside>
    </>
  )
}
