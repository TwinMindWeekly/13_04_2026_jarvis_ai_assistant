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
      className="rounded-xl overflow-hidden"
      style={{
        background: 'var(--bg-input)',
        border: '1px solid var(--border)',
      }}
    >
      {/* Header */}
      <button
        onClick={() => setCollapsed((prev) => !prev)}
        className="w-full flex items-center gap-2.5 px-4 py-3 transition-colors duration-150"
        onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
      >
        <div
          className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0"
          style={{ background: 'rgba(99,102,241,0.18)' }}
        >
          <Cpu size={13} style={{ color: 'var(--accent)' }} />
        </div>

        <span
          className="text-sm font-medium"
          style={{ color: 'var(--accent-hover)' }}
        >
          {t('actions.title')}
        </span>

        {hasActions && (
          <span
            className="text-xs font-semibold px-2 py-0.5 rounded-full"
            style={{
              background: 'rgba(99,102,241,0.15)',
              color: 'var(--accent-hover)',
            }}
          >
            {actions.length}
          </span>
        )}

        <div className="ml-auto">
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
              className="px-3 pb-3 flex flex-col gap-1.5"
              style={{ borderTop: '1px solid var(--border-light)' }}
            >
              {isLoading && !hasActions && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center gap-2.5 px-3 py-2.5"
                >
                  <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                    {t('chat.thinking')}
                  </span>
                  <span className="loading-dots flex gap-1">
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        className="w-1.5 h-1.5 rounded-full"
                        style={{ background: 'var(--accent)', display: 'inline-block' }}
                      />
                    ))}
                  </span>
                </motion.div>
              )}

              {actions.map((action, idx) => (
                <ActionStep key={`${action.tool}-${idx}`} action={action} index={idx} />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
