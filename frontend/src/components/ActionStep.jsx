import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Globe, Monitor, CheckCircle, ChevronRight, Loader2 } from 'lucide-react'
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
      className="shimmer-line"
      style={{ width }}
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
    ? tryFormatJson(
        typeof action.input === 'object' ? JSON.stringify(action.input) : action.input
      )
    : null

  const outputStr = action.output
    ? tryFormatJson(
        typeof action.output === 'object' ? JSON.stringify(action.output) : action.output
      )
    : null

  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.22, delay: index * 0.06, ease: 'easeOut' }}
      className="action-step-card"
    >
      <button
        onClick={() => setExpanded((prev) => !prev)}
        className="action-step-header"
        aria-expanded={expanded}
      >
        {/* Tool icon with status color */}
        <div
          className="d-flex align-items-center justify-content-center rounded-2 flex-shrink-0"
          style={{
            width: 28,
            height: 28,
            background: isRunning
              ? 'rgba(245,158,11,0.12)'
              : 'rgba(34,197,94,0.10)',
            border: `1px solid ${
              isRunning ? 'rgba(245,158,11,0.25)' : 'rgba(34,197,94,0.20)'
            }`,
          }}
        >
          <ToolIcon
            size={14}
            style={{ color: isRunning ? 'var(--warning)' : 'var(--success)' }}
          />
        </div>

        <span
          className="flex-grow-1 text-truncate"
          style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}
        >
          {toolLabel}
        </span>

        <div className="d-flex align-items-center gap-2">
          {isRunning ? (
            <span className="status-badge-running">
              <motion.span
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ duration: 1.2, repeat: Infinity }}
                style={{
                  display: 'inline-block',
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: 'currentColor',
                }}
              />
              {t('actions.running')}
            </span>
          ) : isCompleted ? (
            <span className="status-badge-completed">
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
              className="px-3 pb-3 d-flex flex-column gap-2"
              style={{ borderTop: '1px solid var(--border-light)' }}
            >
              {isRunning && !inputStr && (
                <div className="d-flex flex-column gap-2 pt-2">
                  <ShimmerLine width="75%" />
                  <ShimmerLine width="55%" />
                  <ShimmerLine width="85%" />
                </div>
              )}

              {inputStr && (
                <div className="pt-2">
                  <p
                    className="fw-medium mb-1"
                    style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}
                  >
                    Input
                  </p>
                  <pre
                    style={{
                      fontSize: '0.75rem',
                      borderRadius: 8,
                      padding: '10px',
                      overflowX: 'auto',
                      background: 'var(--bg-code)',
                      border: '1px solid var(--border-light)',
                      color: 'var(--text-secondary)',
                      fontFamily: "'SFMono-Regular', 'Fira Code', monospace",
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      margin: 0,
                    }}
                  >
                    {inputStr}
                  </pre>
                </div>
              )}

              {isRunning && !outputStr && (
                <div className="d-flex align-items-center gap-2 py-1">
                  <Loader2
                    size={12}
                    className="animate-spin"
                    style={{ color: 'var(--warning)' }}
                  />
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Executing...
                  </span>
                </div>
              )}

              {outputStr && (
                <div>
                  <p
                    className="fw-medium mb-1"
                    style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}
                  >
                    Output
                  </p>
                  <pre
                    style={{
                      fontSize: '0.75rem',
                      borderRadius: 8,
                      padding: '10px',
                      overflowX: 'auto',
                      maxHeight: 192,
                      background: 'rgba(34,197,94,0.04)',
                      border: '1px solid rgba(34,197,94,0.12)',
                      color: 'var(--text-secondary)',
                      fontFamily: "'SFMono-Regular', 'Fira Code', monospace",
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      margin: 0,
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
