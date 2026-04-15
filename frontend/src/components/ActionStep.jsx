import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Globe, Monitor, CheckCircle, ChevronDown, ChevronRight, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

const TOOL_ICONS = {
  web_search: Search,
  web_browser: Globe,
  screenshot: Monitor,
}

function tryFormatJson(str) {
  if (typeof str !== 'string') return JSON.stringify(str, null, 2)
  try {
    const parsed = JSON.parse(str)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return str
  }
}

function ShimmerLine({ width = '100%' }) {
  return (
    <div
      className="h-3 rounded"
      style={{
        width,
        background: 'linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.09) 50%, rgba(255,255,255,0.04) 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.6s infinite',
      }}
    />
  )
}

export default function ActionStep({ action, index }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)

  const isRunning = action.status === 'running'
  const isCompleted = action.status === 'completed'

  const ToolIcon = TOOL_ICONS[action.tool] ?? Globe
  const toolLabel = t(`actions.tool.${action.tool}`, { defaultValue: action.tool })

  const inputStr = action.input
    ? tryFormatJson(typeof action.input === 'object' ? JSON.stringify(action.input) : action.input)
    : null

  const outputStr = action.output
    ? tryFormatJson(typeof action.output === 'object' ? JSON.stringify(action.output) : action.output)
    : null

  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.22, delay: index * 0.06, ease: 'easeOut' }}
      className="rounded-lg overflow-hidden mt-1.5"
      style={{
        background: 'var(--bg-main)',
        border: '1px solid var(--border-light)',
      }}
    >
      <button
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors duration-150"
        onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)' }}
        onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
      >
        <div
          className="flex-shrink-0 w-7 h-7 rounded-md flex items-center justify-center"
          style={{
            background: isRunning ? 'rgba(245,158,11,0.12)' : 'rgba(34,197,94,0.1)',
            border: `1px solid ${isRunning ? 'rgba(245,158,11,0.25)' : 'rgba(34,197,94,0.2)'}`,
          }}
        >
          <ToolIcon
            size={14}
            style={{ color: isRunning ? 'var(--warning)' : 'var(--success)' }}
          />
        </div>

        <span
          className="flex-1 text-sm truncate"
          style={{ color: 'var(--text-primary)' }}
        >
          {toolLabel}
        </span>

        <div className="flex items-center gap-2">
          {isRunning ? (
            <span
              className="flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full"
              style={{ background: 'rgba(245,158,11,0.12)', color: 'var(--warning)' }}
            >
              <motion.span
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ duration: 1.2, repeat: Infinity }}
                className="w-1.5 h-1.5 rounded-full bg-current"
              />
              {t('actions.running')}
            </span>
          ) : isCompleted ? (
            <span
              className="flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full"
              style={{ background: 'rgba(34,197,94,0.1)', color: 'var(--success)' }}
            >
              <CheckCircle size={11} />
              {t('actions.completed')}
            </span>
          ) : null}

          <motion.div
            animate={{ rotate: expanded ? 90 : 0 }}
            transition={{ duration: 0.18 }}
          >
            <ChevronRight size={13} style={{ color: 'var(--text-muted)' }} />
          </motion.div>
        </div>
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeInOut' }}
            style={{ overflow: 'hidden' }}
          >
            <div
              className="px-3 pb-3 flex flex-col gap-2"
              style={{ borderTop: '1px solid var(--border-light)' }}
            >
              {isRunning && !inputStr && (
                <div className="flex flex-col gap-2 pt-2">
                  <ShimmerLine width="75%" />
                  <ShimmerLine width="55%" />
                  <ShimmerLine width="85%" />
                </div>
              )}

              {inputStr && (
                <div className="pt-2">
                  <p
                    className="text-xs font-medium mb-1.5"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    Input
                  </p>
                  <pre
                    className="text-xs rounded-lg p-2.5 overflow-x-auto"
                    style={{
                      background: 'var(--bg-code)',
                      border: '1px solid var(--border-light)',
                      color: 'var(--text-secondary)',
                      fontFamily: "'SFMono-Regular', 'Fira Code', monospace",
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                    }}
                  >
                    {inputStr}
                  </pre>
                </div>
              )}

              {isRunning && !outputStr && (
                <div className="flex items-center gap-2 py-1">
                  <Loader2 size={12} className="animate-spin" style={{ color: 'var(--warning)' }} />
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    Executing...
                  </span>
                </div>
              )}

              {outputStr && (
                <div>
                  <p
                    className="text-xs font-medium mb-1.5"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    Output
                  </p>
                  <pre
                    className="text-xs rounded-lg p-2.5 overflow-x-auto max-h-48"
                    style={{
                      background: 'rgba(34,197,94,0.04)',
                      border: '1px solid rgba(34,197,94,0.12)',
                      color: 'var(--text-secondary)',
                      fontFamily: "'SFMono-Regular', 'Fira Code', monospace",
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                    }}
                  >
                    {outputStr}
                  </pre>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
