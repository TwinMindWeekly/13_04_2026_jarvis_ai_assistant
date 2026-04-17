import { useState, memo, useMemo, cloneElement, isValidElement } from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Zap, ChevronDown } from 'lucide-react'
import ActionStep from './ActionStep'
import FilePathLink from './FilePathLink'

const messageVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.22, ease: [0.25, 0.46, 0.45, 0.94] },
  },
}

function StreamingCursor() {
  return (
    <motion.span
      style={{
        display: 'inline-block',
        width: 2,
        height: '1.1em',
        marginLeft: 2,
        borderRadius: 2,
        verticalAlign: 'text-bottom',
        background: 'var(--accent)',
      }}
      animate={{ opacity: [1, 0, 1] }}
      transition={{ duration: 0.9, repeat: Infinity, ease: 'linear' }}
    />
  )
}

function UserAvatar() {
  return <div className="avatar-user">U</div>
}

function AssistantAvatar() {
  return (
    <div className="avatar-assistant">
      <Zap size={15} />
    </div>
  )
}

function InlineActions({ actions }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="inline-actions">
      <button
        onClick={() => setExpanded((prev) => !prev)}
        className="action-summary-btn"
      >
        <Zap size={11} />
        <span>
          {actions.length} action{actions.length !== 1 ? 's' : ''}
        </span>
        <ChevronDown
          size={13}
          style={{
            transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
            transition: 'transform 0.2s',
          }}
        />
      </button>
      {expanded && (
        <div className="inline-actions-list">
          {actions.map((action, idx) => (
            <ActionStep key={idx} action={action} index={idx} />
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Split content into paragraphs and mark the one currently being spoken.
 * Indices align with the paragraphs produced by App.jsx before TTS dispatch.
 */
function splitParagraphs(content, speakingParagraphIndex) {
  const paragraphs = content.split(/\n\n+/)
  return paragraphs.map((text, i) => ({
    text,
    active: i === speakingParagraphIndex,
  }))
}

// Custom ReactMarkdown components that linkify file paths in text nodes
const mdComponents = {
  p: ({ children }) => <p>{renderWithFilePaths(children)}</p>,
  li: ({ children }) => <li>{renderWithFilePaths(children)}</li>,
  td: ({ children }) => <td>{renderWithFilePaths(children)}</td>,
  code: ({ children, className }) => {
    // Only linkify inline code (no language className), not code blocks
    if (className) return <code className={className}>{children}</code>
    return <code>{renderWithFilePaths(children)}</code>
  },
}

function renderWithFilePaths(children) {
  if (children == null || typeof children === 'boolean') return children
  if (typeof children === 'string') return <FilePathLink>{children}</FilePathLink>
  if (Array.isArray(children)) {
    return children.map((child, i) => {
      if (typeof child === 'string') return <FilePathLink key={i}>{child}</FilePathLink>
      if (isValidElement(child)) {
        return cloneElement(child, { key: child.key ?? i }, renderWithFilePaths(child.props.children))
      }
      return child
    })
  }
  // Recurse into React elements (e.g. <strong>D:\path.docx</strong>) so file
  // paths nested inside bold/italic/links are still linkified.
  if (isValidElement(children)) {
    return cloneElement(children, {}, renderWithFilePaths(children.props.children))
  }
  return children
}

function MessageBubble({ message, isStreaming = false, speakingParagraphIndex = -1 }) {
  const isUser = message.role === 'user'
  const actionCount = message.actions?.length ?? 0
  const label = isUser ? 'You' : 'JARVIS'
  const hasSpeaking = !isUser && speakingParagraphIndex >= 0

  return (
    <motion.div
      variants={messageVariants}
      initial="hidden"
      animate="visible"
      className="message-row"
    >
      {/* Inner content — full width with comfortable side padding */}
      <div className="w-100 px-4 d-flex gap-3">
        {isUser ? <UserAvatar /> : <AssistantAvatar />}

        <div className="d-flex flex-column gap-1 flex-grow-1" style={{ minWidth: 0 }}>
          <span
            className="fw-semibold"
            style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}
          >
            {label}
          </span>

          {actionCount > 0 && <InlineActions actions={message.actions} />}

          {isUser ? (
            <p
              style={{
                margin: 0,
                fontSize: '1rem',
                lineHeight: 1.75,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-words',
                color: 'var(--text-primary)',
              }}
            >
              {message.content}
            </p>
          ) : hasSpeaking ? (
            <div
              className="markdown-content"
              style={{ fontSize: '1rem', lineHeight: 1.75, color: 'var(--text-primary)' }}
            >
              {splitParagraphs(message.content, speakingParagraphIndex).map((para, i) => (
                <div key={i} className={para.active ? 'speaking-paragraph' : ''}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{para.text}</ReactMarkdown>
                </div>
              ))}
              {isStreaming && <StreamingCursor />}
            </div>
          ) : (
            <div
              className="markdown-content"
              style={{ fontSize: '1rem', lineHeight: 1.75, color: 'var(--text-primary)' }}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                {message.content}
              </ReactMarkdown>
              {isStreaming && <StreamingCursor />}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

export default memo(MessageBubble)
