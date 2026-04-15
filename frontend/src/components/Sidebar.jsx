import { motion, AnimatePresence } from 'framer-motion'
import { SquarePen, Settings, MessageSquare, PanelLeft, Zap, FileText, Network } from 'lucide-react'
import { useTranslation } from 'react-i18next'

const SIDEBAR_WIDTH = 260

function SidebarNavItem({ icon: Icon, label, onClick }) {
  return (
    <button className="sidebar-nav-item" onClick={onClick}>
      <Icon size={18} />
      <span>{label}</span>
    </button>
  )
}

export default function Sidebar({
  isOpen,
  onToggle,
  onNewChat,
  onOpenSettings,
  onOpenDocuments,
  onOpenGraph,
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
            className="sidebar-overlay d-lg-none"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onToggle}
          />
        )}
      </AnimatePresence>

      {/* Sidebar panel */}
      <motion.aside
        className="sidebar-panel"
        initial={false}
        animate={{ width: isOpen ? SIDEBAR_WIDTH : 0 }}
        transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
        aria-hidden={!isOpen}
      >
        <div className="sidebar-inner">
          {/* Top: toggle + new chat */}
          <div className="d-flex align-items-center justify-content-between px-2 pt-3 pb-1">
            <button
              onClick={onToggle}
              className="sidebar-icon-btn"
              aria-label="Toggle sidebar"
            >
              <PanelLeft size={20} />
            </button>

            <button
              onClick={onNewChat}
              className="sidebar-icon-btn"
              aria-label={t('sidebar.newChat')}
              title={t('sidebar.newChat')}
            >
              <SquarePen size={20} />
            </button>
          </div>

          {/* Navigation items */}
          <div className="px-2 py-1">
            <SidebarNavItem
              icon={SquarePen}
              label={t('sidebar.newChat')}
              onClick={onNewChat}
            />
            <SidebarNavItem
              icon={FileText}
              label={t('sidebar.documents', 'Documents')}
              onClick={onOpenDocuments}
            />
            <SidebarNavItem
              icon={Network}
              label={t('sidebar.graph', 'Knowledge Graph')}
              onClick={onOpenGraph}
            />
          </div>

          {/* Chat history */}
          <div className="flex-grow-1 px-2 py-2 overflow-auto">
            <p
              className="px-3 py-2 text-uppercase fw-medium"
              style={{
                fontSize: '0.7rem',
                letterSpacing: '0.08em',
                color: 'var(--text-muted)',
              }}
            >
              Recents
            </p>
            <div className="d-flex flex-column align-items-center justify-content-center gap-2 py-4">
              <MessageSquare size={18} style={{ color: 'var(--text-muted)' }} />
              <span
                className="text-center"
                style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}
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
                className="d-flex align-items-center gap-2 px-3 py-2 mb-1 rounded-3"
                style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}
              >
                <div
                  className="d-flex align-items-center justify-content-center rounded-circle flex-shrink-0"
                  style={{ width: 20, height: 20, background: 'var(--accent)' }}
                >
                  <Zap size={10} color="#fff" />
                </div>
                <span className="text-truncate">
                  {currentProvider} · {currentModel}
                </span>
              </div>
            )}

            <SidebarNavItem
              icon={Settings}
              label={t('sidebar.settings')}
              onClick={onOpenSettings}
            />
          </div>
        </div>
      </motion.aside>
    </>
  )
}
