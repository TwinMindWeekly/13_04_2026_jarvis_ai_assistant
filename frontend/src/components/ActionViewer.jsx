import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, Cpu } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import ActionStep from './ActionStep'

export default function ActionViewer({ actions = [], isLoading = false }) {
  const { t } = useTranslation()
  const [collapsed, setCollapsed] = useState(false)

  const hasActions = actions.length > 0
  const showPanel = hasActions || isLoading

  if (!showPanel) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
      className="action-card"
    >
      {/* Header */}
      <button
        onClick={() => setCollapsed((prev) => !prev)}
        className="action-card-header"
        aria-expanded={!collapsed}
      >
        <div
          className="d-flex align-items-center justify-content-center rounded-2 flex-shrink-0"
          style={{
            width: 24,
            height: 24,
            background: 'rgba(99,102,241,0.18)',
          }}
        >
          <Cpu size={13} style={{ color: 'var(--accent)' }} />
        </div>

        <span
          className="fw-medium"
          style={{ fontSize: '0.875rem', color: 'var(--accent-hover)' }}
        >
          {t('actions.title')}
        </span>

        {hasActions && (
          <span
            className="fw-semibold px-2"
            style={{
              fontSize: '0.75rem',
              borderRadius: 999,
              background: 'rgba(99,102,241,0.15)',
              color: 'var(--accent-hover)',
              paddingTop: 2,
              paddingBottom: 2,
            }}
          >
            {actions.length}
          </span>
        )}

        <div className="ms-auto">
          <motion.div
            animate={{ rotate: collapsed ? -90 : 0 }}
            transition={{ duration: 0.18 }}
          >
            <ChevronDown size={16} style={{ color: 'var(--text-muted)' }} />
          </motion.div>
        </div>
      </button>

      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeInOut' }}
            style={{ overflow: 'hidden' }}
          >
            <div
              className="px-3 pb-3 d-flex flex-column"
              style={{
                gap: 6,
                borderTop: '1px solid var(--border-light)',
              }}
            >
              {isLoading && !hasActions && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="d-flex align-items-center gap-2 px-3 py-2"
                >
                  <span
                    style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}
                  >
                    {t('chat.thinking')}
                  </span>
                  <span className="loading-dots d-flex gap-1">
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          background: 'var(--accent)',
                          display: 'inline-block',
                        }}
                      />
                    ))}
                  </span>
                </motion.div>
              )}

              {actions.map((action, idx) => (
                <ActionStep
                  key={`${action.tool}-${idx}`}
                  action={action}
                  index={idx}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
