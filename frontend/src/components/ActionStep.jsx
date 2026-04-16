import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search,
  Globe,
  Monitor,
  MousePointer,
  FolderOpen,
  Terminal,
  Clipboard,
  Bell,
  Mail,
  Image,
  Code,
  BookOpen,
  Play,
  CheckCircle,
  ChevronRight,
  Loader2,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'

const TOOL_ICONS = {
  web_search: Search,
  web_browser: Globe,
  screenshot: Monitor,
  desktop_control: MousePointer,
  browser_control: Globe,
  file_manager: FolderOpen,
  app_launcher: Play,
  shell_exec: Terminal,
  code_runner: Code,
  email: Mail,
  clipboard: Clipboard,
  system_notification: Bell,
  image_generator: Image,
  skill_manager: BookOpen,
  rag_search: Search,
}

function getActionSummary(action) {
  const input = action.input || {}
  switch (action.tool) {
    case 'web_search':
      return `Searching: "${input.query || ''}"`
    case 'web_browser':
      return `Opening: ${input.url || ''}`
    case 'browser_control':
      return `Browser: ${input.action || ''} ${input.url || input.text || ''}`
    case 'screenshot':
      return 'Taking screenshot'
    case 'desktop_control':
      return `Desktop: ${input.action || ''} ${input.text || ''}`
    case 'file_manager':
      return `File: ${input.action || ''} ${input.path || ''}`
    case 'app_launcher':
      return `Launch: ${input.app || ''}`
    case 'shell_exec':
      return `Shell: ${(input.command || '').substring(0, 60)}`
    case 'code_runner':
      return `Run ${input.language || 'code'}`
    case 'email':
      return `Email: ${input.action || ''}`
    case 'clipboard':
      return `Clipboard: ${input.action || ''}`
    case 'system_notification':
      return `Notify: ${input.title || ''}`
    case 'image_generator':
      return `Generate image: "${(input.prompt || '').substring(0, 40)}"`
    case 'skill_manager':
      return `Skills: ${input.action || ''}`
    default:
      return action.tool
  }
}

function formatOutput(output) {
  if (!output) return null
  try {
    const parsed = JSON.parse(output)
    if (Array.isArray(parsed)) {
      return parsed
        .map(
          (item, i) =>
            `${i + 1}. ${item.title || item.name || ''}\n   ${item.snippet || item.body || item.url || ''}`
        )
        .join('\n')
    }
    if (typeof parsed === 'object') {
      return Object.entries(parsed)
        .map(([k, v]) => `${k}: ${v}`)
        .join('\n')
    }
    return String(parsed)
  } catch {
    return output
  }
}

function ShimmerLine({ width = '100%' }) {
  return <div className="shimmer-line" style={{ width }} />
}

const OUTPUT_TRUNCATE_LENGTH = 200

export default function ActionStep({ action, index }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const [outputExpanded, setOutputExpanded] = useState(false)

  const isRunning = action.status === 'running'
  const isCompleted = action.status === 'completed'

  const ToolIcon = TOOL_ICONS[action.tool] ?? Globe
  const summary = getActionSummary(action)

  const inputStr = action.input
    ? typeof action.input === 'object'
      ? JSON.stringify(action.input, null, 2)
      : action.input
    : null

  const rawOutput = action.output
    ? typeof action.output === 'object'
      ? JSON.stringify(action.output)
      : action.output
    : null

  const formattedOutput = rawOutput ? formatOutput(rawOutput) : null
  const isLongOutput = formattedOutput && formattedOutput.length > OUTPUT_TRUNCATE_LENGTH
  const displayedOutput =
    formattedOutput && isLongOutput && !outputExpanded
      ? formattedOutput.substring(0, OUTPUT_TRUNCATE_LENGTH) + '…'
      : formattedOutput

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
          {summary}
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

              {isRunning && !formattedOutput && (
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

              {formattedOutput && (
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
                      maxHeight: outputExpanded ? 'none' : 192,
                      background: 'rgba(34,197,94,0.04)',
                      border: '1px solid rgba(34,197,94,0.12)',
                      color: 'var(--text-secondary)',
                      fontFamily: "'SFMono-Regular', 'Fira Code', monospace",
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      margin: 0,
                    }}
                  >
                    {displayedOutput}
                  </pre>
                  {isLongOutput && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setOutputExpanded((prev) => !prev)
                      }}
                      style={{
                        marginTop: 4,
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        fontSize: '0.72rem',
                        color: 'var(--accent-hover)',
                        padding: '2px 0',
                      }}
                    >
                      {outputExpanded ? 'Show less' : 'Show more'}
                    </button>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
