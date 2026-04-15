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
      className="rounded-2xl overflow-hidden mx-1"
      style={{
        background: 'rgba(99,102,241,0.05)',
        border: '1px solid rgba(99,102,241,0.18)',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
      }}
    >
      {/* Header */}
      <button
        onClick={() => setCollapsed((prev) => !prev)}
        className="w-full flex items-center gap-2.5 px-4 py-2.5 transition-colors duration-150 hover:bg-white/[0.03]"
      >
        <div
          className="w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0"
          style={{
            background: 'rgba(99,102,241,0.18)',
          }}
        >
          <Cpu size={11} style={{ color: 'var(--accent)' }} />
        </div>

        <span
          className="text-xs font-semibold uppercase tracking-widest"
          style={{ color: 'var(--accent)' }}
        >
          {t('actions.title')}
        </span>

        {hasActions && (
          <span
            className="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
            style={{
              background: 'rgba(99,102,241,0.2)',
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
            <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />
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
            <div className="px-3 pb-3 flex flex-col gap-1.5">
              {isLoading && !hasActions && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center gap-2.5 px-3 py-2.5"
                >
                  <span
                    className="text-sm"
                    style={{ color: 'var(--text-secondary)' }}
                  >
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
