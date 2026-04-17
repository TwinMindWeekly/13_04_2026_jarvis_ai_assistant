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
  local_search: Search,
}

function getActionSummary(action) {
  const input = action.input || {}
  switch (action.tool) {
    case 'web_search':
      return `Tìm kiếm: "${input.query || ''}"`
    case 'web_browser':
      return `Mở: ${input.url || ''}`
    case 'browser_control':
      return `Trình duyệt: ${input.action || ''} ${input.url || input.text || ''}`
    case 'screenshot':
      return 'Chụp màn hình'
    case 'desktop_control':
      return `Thao tác: ${input.action || ''} ${input.text || ''}`
    case 'file_manager':
      return `File: ${input.action || ''} ${input.path || ''}`
    case 'app_launcher':
      return `Mở: ${input.app || ''}`
    case 'shell_exec':
      return `Lệnh: ${(input.command || '').substring(0, 60)}`
    case 'code_runner':
      return `Chạy ${input.language || 'code'}`
    case 'email':
      return `Email: ${input.action || ''}`
    case 'clipboard':
      return `Clipboard: ${input.action || ''}`
    case 'system_notification':
      return `Thông báo: ${input.title || ''}`
    case 'image_generator':
      return `Tạo ảnh: "${(input.prompt || '').substring(0, 40)}"`
    case 'skill_manager':
      return `Kỹ năng: ${input.action || ''}`
    case 'rag_search':
      return `Tìm tài liệu: "${input.query || ''}"`
    case 'local_search':
      return `Tìm file: "${input.query || ''}" ${input.mode === 'content' ? '(nội dung)' : ''}`
    default:
      return action.tool
  }
}

function formatOutput(output) {
  if (!output) return null
  try {
    const parsed = JSON.parse(output)
    return _formatParsed(parsed)
  } catch {
    return output.length > 500 ? output.substring(0, 500) + '…' : output
  }
}

function _formatParsed(obj) {
  if (!obj) return ''

  // ToolResult: { success, data, error, metadata }
  if ('success' in obj && 'data' in obj) {
    if (!obj.success) return `❌ ${obj.error || 'Lỗi'}`
    return _formatParsed(obj.data)
  }

  // Local search / RAG results: { results: [...], summary }
  if (obj.summary && Array.isArray(obj.results)) {
    if (obj.results.length === 0) return obj.summary
    const items = obj.results.slice(0, 5).map((r, i) => {
      const name = r.name || r.filename || r.path || ''
      const matches = r.matches?.map((m) => `  L${m.line}: ${m.text}`).join('\n') || ''
      return `${i + 1}. ${name}${matches ? '\n' + matches : ''}`
    }).join('\n')
    return `${obj.summary}\n\n${items}`
  }

  // Web search results: array of {title, snippet, url}
  if (Array.isArray(obj)) {
    return obj.slice(0, 5).map((item, i) => {
      const title = item.title || item.name || item.label || ''
      const detail = item.snippet || item.body || item.content?.substring(0, 100) || item.url || ''
      return `${i + 1}. ${title}${detail ? '\n   ' + detail : ''}`
    }).join('\n')
  }

  // Simple string
  if (typeof obj === 'string') return obj

  // Generic object — show key: value
  const entries = Object.entries(obj).filter(([, v]) => v != null && v !== '')
  return entries.map(([k, v]) => {
    const val = typeof v === 'object' ? JSON.stringify(v).substring(0, 100) : String(v)
    return `${k}: ${val}`
  }).join('\n')
}

/** Format input as friendly text instead of raw JSON. */
function formatInput(tool, input) {
  if (!input) return null
  if (typeof input === 'string') return input
  const parts = []
  for (const [k, v] of Object.entries(input)) {
    if (v == null || v === '') continue
    parts.push(`${k}: ${v}`)
  }
  return parts.join('\n') || null
}

/** Extract actual content from tool output — handles `content='...'` pattern from LangChain. */
function _extractContent(output) {
  if (!output) return null
  const str = typeof output === 'object' ? JSON.stringify(output) : String(output)
  // LangChain wraps tool output as `content='{"results":...}'` — extract the inner JSON
  const contentMatch = str.match(/^content='([\s\S]*)'$/)
  if (contentMatch) return contentMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\\\/g, '\\')
  const contentMatch2 = str.match(/^content="([\s\S]*)"$/)
  if (contentMatch2) return contentMatch2[1].replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\\\/g, '\\')
  return str
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

  const inputStr = action.input ? formatInput(action.tool, action.input) : null

  const rawOutput = action.output ? _extractContent(action.output) : null
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
